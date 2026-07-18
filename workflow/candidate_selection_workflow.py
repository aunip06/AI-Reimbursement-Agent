from __future__ import annotations

from models.candidate_selection import (
    CandidateEvaluation,
    PageCandidateSelectionResult,
)
from models.claim import Claim
from models.receipt_candidate_evidence import (
    PageReceiptCandidateEvidence,
)
from tools.candidate_match_tool import (
    calculate_semantic_score,
    is_strict_candidate_match,
    score_candidate_locally,
)
from workflow.reimbursement_workflow import (
    process_claim_ocr,
)


MAX_AGENT_CANDIDATES = 3

GENERAL_SHORTLIST_SCORE = 20.0

MINIMUM_UNIQUE_SEMANTIC_SCORE = 70.0

MINIMUM_SEMANTIC_SCORE_GAP = 20.0

AMBIGUOUS_SCORE_GAP = 12.0


def create_local_evaluation(
    local_result: dict,
    *,
    shortlisted: bool = False,
) -> CandidateEvaluation:
    """
    Create a candidate evaluation before agent analysis.
    """

    return CandidateEvaluation(
        **local_result,
        shortlisted=shortlisted,
        analysis=None,
        final_decision=None,
        semantic_score=0.0,
        strict_match=False,
    )


def select_candidate_numbers_for_analysis(
    local_results: list[dict],
) -> set[int]:
    """
    Select the strongest candidates for isolated agent analysis.

    Candidate text is never combined with another candidate.
    """

    ranked_results = sorted(
        local_results,
        key=lambda result: (
            result["local_score"]
        ),
        reverse=True,
    )

    shortlisted = [
        result["candidate_no"]
        for result in ranked_results
        if (
            result["local_score"]
            >= GENERAL_SHORTLIST_SCORE
        )
    ]

    if not shortlisted and ranked_results:
        shortlisted = [
            ranked_results[0][
                "candidate_no"
            ]
        ]

    return set(
        shortlisted[
            :MAX_AGENT_CANDIDATES
        ]
    )


def select_candidate_for_claim(
    claim: Claim,
    page_evidence: PageReceiptCandidateEvidence,
) -> PageCandidateSelectionResult:
    """
    Select one independent receipt candidate for a claim.

    Selection identifies which screenshot belongs to the claim.
    It does not approve reimbursement payment.
    """

    if page_evidence.detection.blank_page:
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="BLANK_PAGE",
            selected_candidate_no=None,
            candidate_evaluations=[],
            reasons=[
                (
                    "The referenced PDF page is visually blank."
                )
            ],
        )

    readable_candidates = [
        candidate_evidence
        for candidate_evidence
        in page_evidence.candidates
        if candidate_evidence.text_found
    ]

    if not readable_candidates:
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="NO_CANDIDATES",
            selected_candidate_no=None,
            candidate_evaluations=[],
            reasons=[
                (
                    "No detected screenshot or receipt candidate "
                    "contained readable evidence."
                )
            ],
        )

    local_results = [
        score_candidate_locally(
            claim=claim,
            candidate_evidence=(
                candidate_evidence
            ),
        )
        for candidate_evidence
        in readable_candidates
    ]

    # When the page contains only one readable candidate,
    # it is the only possible evidence region. Claim mismatches
    # are handled later by the reimbursement safety gate.
    if len(readable_candidates) == 1:
        only_result = local_results[0]

        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="UNIQUE_MATCH",
            selected_candidate_no=(
                only_result[
                    "candidate_no"
                ]
            ),
            candidate_evaluations=[
                create_local_evaluation(
                    only_result
                )
            ],
            reasons=[
                (
                    "The page contained exactly one readable "
                    "receipt candidate."
                ),
                (
                    "Claim-field mismatches will be evaluated "
                    "by the reimbursement safety gate."
                ),
            ],
        )

    transaction_candidates = [
        result
        for result in local_results
        if result[
            "exact_transaction_id_found"
        ]
    ]

    invoice_candidates = [
        result
        for result in local_results
        if result[
            "exact_invoice_no_found"
        ]
    ]

    exact_identifier_candidates = {
        result["candidate_no"]
        for result in (
            transaction_candidates
            + invoice_candidates
        )
    }

    # An exact transaction or invoice identifier uniquely
    # associates the claim with one isolated screenshot.
    if len(exact_identifier_candidates) == 1:
        selected_candidate_no = next(
            iter(
                exact_identifier_candidates
            )
        )

        evaluations = [
            create_local_evaluation(
                result,
                shortlisted=(
                    result[
                        "candidate_no"
                    ]
                    == selected_candidate_no
                ),
            )
            for result in local_results
        ]

        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="UNIQUE_MATCH",
            selected_candidate_no=(
                selected_candidate_no
            ),
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "Exactly one independent candidate contained "
                    "the claimed transaction or invoice identifier."
                )
            ],
        )

    if len(exact_identifier_candidates) > 1:
        evaluations = [
            create_local_evaluation(
                result,
                shortlisted=(
                    result[
                        "candidate_no"
                    ]
                    in exact_identifier_candidates
                ),
            )
            for result in local_results
        ]

        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="AMBIGUOUS_MATCH",
            selected_candidate_no=None,
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "The claimed identifier appeared in more "
                    "than one independent candidate."
                ),
                (
                    "Automatic candidate selection was blocked."
                ),
            ],
        )

    shortlisted_numbers = (
        select_candidate_numbers_for_analysis(
            local_results
        )
    )

    evidence_by_candidate_number = {
        (
            candidate_evidence
            .candidate
            .candidate_no
        ): candidate_evidence
        for candidate_evidence
        in readable_candidates
    }

    evaluations: list[
        CandidateEvaluation
    ] = []

    for local_result in local_results:
        candidate_no = (
            local_result[
                "candidate_no"
            ]
        )

        shortlisted = (
            candidate_no
            in shortlisted_numbers
        )

        analysis = None
        final_decision = None
        semantic_score = 0.0
        strict_match = False

        if shortlisted:
            candidate_evidence = (
                evidence_by_candidate_number[
                    candidate_no
                ]
            )

            processing_result = (
                process_claim_ocr(
                    claim=claim,
                    ocr_text=(
                        candidate_evidence
                        .combined_evidence_text
                    ),
                    pdf_exists=True,
                    page_exists=True,
                    duplicate_page_reference=False,
                )
            )

            analysis = (
                processing_result.analysis
            )

            final_decision = (
                processing_result.final_decision
            )

            semantic_score = (
                calculate_semantic_score(
                    analysis
                )
            )

            strict_match = (
                is_strict_candidate_match(
                    claim=claim,
                    analysis=analysis,
                )
            )

        evaluations.append(
            CandidateEvaluation(
                **local_result,
                shortlisted=shortlisted,
                analysis=analysis,
                final_decision=final_decision,
                semantic_score=(
                    semantic_score
                ),
                strict_match=(
                    strict_match
                ),
            )
        )

    strict_matches = [
        evaluation
        for evaluation in evaluations
        if evaluation.strict_match
    ]

    if len(strict_matches) == 1:
        selected = strict_matches[0]

        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="UNIQUE_MATCH",
            selected_candidate_no=(
                selected.candidate_no
            ),
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "Exactly one independently analyzed candidate "
                    "satisfied the strict claim-selection rules."
                )
            ],
        )

    if len(strict_matches) > 1:
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="AMBIGUOUS_MATCH",
            selected_candidate_no=None,
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "More than one independently analyzed candidate "
                    "satisfied the strict selection rules."
                )
            ],
        )

    analyzed_evaluations = sorted(
        [
            evaluation
            for evaluation in evaluations
            if evaluation.analysis is not None
            and evaluation.analysis.receipt.bill_found
        ],
        key=lambda evaluation: (
            evaluation.semantic_score,
            evaluation.local_score,
        ),
        reverse=True,
    )

    if not analyzed_evaluations:
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="NO_MATCH",
            selected_candidate_no=None,
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "No isolated candidate contained usable "
                    "receipt evidence for this claim."
                )
            ],
        )

    top_candidate = (
        analyzed_evaluations[0]
    )

    second_score = (
        analyzed_evaluations[1].semantic_score
        if len(analyzed_evaluations) > 1
        else 0.0
    )

    score_gap = (
        top_candidate.semantic_score
        - second_score
    )

    # A uniquely stronger candidate can still be selected when
    # one claim field is wrong. The final safety gate will then
    # return AMOUNT_MISMATCH, VENDOR_MISMATCH, etc.
    if (
        top_candidate.semantic_score
        >= MINIMUM_UNIQUE_SEMANTIC_SCORE
        and (
            len(analyzed_evaluations) == 1
            or score_gap
            >= MINIMUM_SEMANTIC_SCORE_GAP
        )
    ):
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="UNIQUE_MATCH",
            selected_candidate_no=(
                top_candidate.candidate_no
            ),
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "One candidate was substantially more relevant "
                    "than every other candidate on the page."
                ),
                (
                    f"Semantic score gap: {score_gap:.1f}."
                ),
            ],
        )

    if (
        len(analyzed_evaluations) > 1
        and top_candidate.semantic_score >= 50
        and score_gap <= AMBIGUOUS_SCORE_GAP
    ):
        return PageCandidateSelectionResult(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="AMBIGUOUS_MATCH",
            selected_candidate_no=None,
            candidate_evaluations=(
                evaluations
            ),
            reasons=[
                (
                    "Multiple independent candidates received "
                    "similar claim-relevance scores."
                ),
                (
                    "Automatic candidate selection was blocked."
                ),
            ],
        )

    return PageCandidateSelectionResult(
        expense_id=claim.expense_id,
        pdf_file_name=(
            claim.monthly_pdf_name
        ),
        page_number=(
            claim.receipt_page_no
        ),
        status="NO_MATCH",
        selected_candidate_no=None,
        candidate_evaluations=(
            evaluations
        ),
        reasons=[
            (
                "No independent candidate was sufficiently "
                "associated with this claim."
            )
        ],
    )