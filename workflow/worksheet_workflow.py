from __future__ import annotations

from collections import Counter
from pathlib import Path

from models.claim import Claim
from models.final_decision import FinalStatus
from models.worksheet_processing_result import (
    WorksheetClaimResult,
    WorksheetProcessingResult,
)
from tools.excel_tool import (
    read_claims_from_worksheet,
)


PageReference = tuple[str, int]


def get_page_reference(
    claim: Claim,
) -> PageReference:
    """
    Return the normalized PDF-page reference.

    Retained for backward compatibility with older tests.
    Production duplicate protection now uses selected
    receipt-candidate fingerprints.
    """

    return (
        claim.monthly_pdf_name.casefold(),
        claim.receipt_page_no,
    )


def find_duplicate_page_references(
    claims: list[Claim],
) -> set[PageReference]:
    """
    Return repeated PDF-page references.

    This helper is retained for compatibility only.
    Repeated pages are no longer automatically rejected,
    because one page may contain multiple separate receipts.
    """

    reference_counts = Counter(
        get_page_reference(claim)
        for claim in claims
    )

    return {
        reference
        for reference, count
        in reference_counts.items()
        if count > 1
    }


def map_local_evidence_status(
    evidence_status: str,
) -> FinalStatus:
    """
    Convert local evidence failures into final statuses.
    """

    status_map: dict[str, FinalStatus] = {
        "PDF_MISSING": "PDF_MISSING",
        "PAGE_MISSING": "PAGE_MISSING",
        "TEXT_NOT_FOUND": "OCR_UNCLEAR",
        "EMPTY_PAGE": "EMPTY_PAGE",
        "BILL_NOT_FOUND_ON_PAGE": (
            "BILL_NOT_FOUND_ON_PAGE"
        ),
        "AMBIGUOUS_RECEIPT_SELECTION": (
            "AMBIGUOUS_RECEIPT_SELECTION"
        ),
    }

    return status_map.get(
        evidence_status,
        "POSSIBLE_MATCH_NOT_APPROVED",
    )


def get_selected_receipt_fingerprint(
    result: WorksheetClaimResult,
) -> str | None:
    """
    Return the fingerprint of the exact receipt candidate
    selected for one claim.
    """

    workflow_result = result.workflow_result

    if workflow_result is None:
        return None

    return (
        workflow_result
        .evidence
        .selected_candidate_fingerprint
    )


def find_duplicate_receipt_fingerprints(
    results: list[WorksheetClaimResult],
) -> set[str]:
    """
    Find selected receipt candidates used by multiple claims.

    Claims referencing the same page but selecting different
    candidates are not duplicates.
    """

    fingerprints = [
        fingerprint
        for result in results
        if (
            fingerprint
            := get_selected_receipt_fingerprint(
                result
            )
        )
    ]

    fingerprint_counts = Counter(
        fingerprints
    )

    return {
        fingerprint
        for fingerprint, count
        in fingerprint_counts.items()
        if count > 1
    }


def mark_as_duplicate_receipt(
    result: WorksheetClaimResult,
) -> WorksheetClaimResult:
    """
    Replace a claim's decision with a non-payable duplicate
    receipt decision while preserving its audit evidence.
    """

    duplicate_message = (
        "The same independently detected receipt candidate "
        "was selected for multiple reimbursement claims. "
        "Every claim using this receipt was blocked."
    )

    workflow_result = (
        result.workflow_result
    )

    if (
        workflow_result is None
        or workflow_result.processing_result
        is None
    ):
        return result.model_copy(
            deep=True,
            update={
                "final_status": (
                    "DUPLICATE_RECEIPT_REFERENCE"
                ),
                "auto_payable": False,
                "message": duplicate_message,
            },
        )

    processing_result = (
        workflow_result.processing_result
    )

    final_decision = (
        processing_result.final_decision
    )

    updated_safety_checks = dict(
        final_decision.safety_checks
    )

    updated_safety_checks[
        "unique_receipt_reference"
    ] = False

    updated_reasons = [
        duplicate_message,
        *final_decision.reasons,
    ]

    updated_final_decision = (
        final_decision.model_copy(
            deep=True,
            update={
                "final_status": (
                    "DUPLICATE_RECEIPT_REFERENCE"
                ),
                "auto_payable": False,
                "safety_checks": (
                    updated_safety_checks
                ),
                "reasons": (
                    updated_reasons
                ),
            },
        )
    )

    updated_processing_result = (
        processing_result.model_copy(
            deep=True,
            update={
                "final_decision": (
                    updated_final_decision
                ),
                "message": (
                    duplicate_message
                ),
            },
        )
    )

    updated_workflow_result = (
        workflow_result.model_copy(
            deep=True,
            update={
                "processing_result": (
                    updated_processing_result
                ),
                "message": (
                    duplicate_message
                ),
            },
        )
    )

    return result.model_copy(
        deep=True,
        update={
            "final_status": (
                "DUPLICATE_RECEIPT_REFERENCE"
            ),
            "auto_payable": False,
            "message": duplicate_message,
            "workflow_result": (
                updated_workflow_result
            ),
        },
    )


def apply_duplicate_receipt_protection(
    results: list[WorksheetClaimResult],
) -> list[WorksheetClaimResult]:
    """
    Block every claim using a duplicated receipt candidate.
    """

    duplicate_fingerprints = (
        find_duplicate_receipt_fingerprints(
            results
        )
    )

    protected_results: list[
        WorksheetClaimResult
    ] = []

    for result in results:
        fingerprint = (
            get_selected_receipt_fingerprint(
                result
            )
        )

        if (
            fingerprint
            and fingerprint
            in duplicate_fingerprints
        ):
            protected_results.append(
                mark_as_duplicate_receipt(
                    result
                )
            )

        else:
            protected_results.append(
                result
            )

    return protected_results


def process_monthly_worksheet(
    excel_path: str | Path,
    worksheet_name: str,
    pdf_directory: str | Path,
) -> WorksheetProcessingResult:
    """
    Process every valid claim in one monthly worksheet.

    Multiple claims may reference the same PDF page. Each claim
    is matched to an isolated receipt candidate first.

    Duplicate protection is applied only after candidate
    selection and uses the selected receipt fingerprint.
    """

    # Local import prevents EasyOCR and PyTorch from loading
    # during Excel-only and helper-function tests.
    from workflow.end_to_end_workflow import (
        process_claim_from_files,
    )

    claims, excel_errors = (
        read_claims_from_worksheet(
            file_path=excel_path,
            worksheet_name=worksheet_name,
        )
    )

    results: list[
        WorksheetClaimResult
    ] = []

    for claim in claims:
        workflow_result = (
            process_claim_from_files(
                claim=claim,
                pdf_directory=pdf_directory,
            )
        )

        if (
            workflow_result
            .processing_result
            is None
        ):
            final_status = (
                map_local_evidence_status(
                    workflow_result
                    .evidence
                    .status
                )
            )

            results.append(
                WorksheetClaimResult(
                    claim=claim,
                    result_source=(
                        "local_validation"
                    ),
                    final_status=(
                        final_status
                    ),
                    auto_payable=False,
                    message=(
                        workflow_result.message
                    ),
                    workflow_result=(
                        workflow_result
                    ),
                )
            )

            continue

        processing_result = (
            workflow_result.processing_result
        )

        final_decision = (
            processing_result.final_decision
        )

        results.append(
            WorksheetClaimResult(
                claim=claim,
                result_source=(
                    processing_result
                    .result_source
                ),
                final_status=(
                    final_decision
                    .final_status
                ),
                auto_payable=(
                    final_decision
                    .auto_payable
                ),
                message=(
                    final_decision.reasons[0]
                ),
                workflow_result=(
                    workflow_result
                ),
            )
        )

    results = (
        apply_duplicate_receipt_protection(
            results
        )
    )

    approved_count = sum(
        1
        for result in results
        if result.auto_payable
    )

    exception_count = (
        len(results)
        - approved_count
    )

    duplicate_receipt_claims = sum(
        1
        for result in results
        if (
            result.final_status
            == "DUPLICATE_RECEIPT_REFERENCE"
        )
    )

    completed_claims = sum(
        1
        for result in results
        if result.result_source
        in {
            "cache",
            "openai",
        }
    )

    return WorksheetProcessingResult(
        worksheet_name=worksheet_name,
        total_claims=len(claims),
        completed_claims=(
            completed_claims
        ),
        approved_count=(
            approved_count
        ),
        exception_count=(
            exception_count
        ),

        # The model currently retains this legacy field name.
        # It now stores duplicate receipt-claim count.
        duplicate_page_claims=(
            duplicate_receipt_claims
        ),

        excel_errors=excel_errors,
        results=results,
    )