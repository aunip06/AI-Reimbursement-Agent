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
    Return a normalized monthly PDF and page-number reference.
    """

    return (
        claim.monthly_pdf_name.casefold(),
        claim.receipt_page_no,
    )


def find_duplicate_page_references(
    claims: list[Claim],
) -> set[PageReference]:
    """
    Find every PDF/page combination referenced by more
    than one reimbursement claim.

    All claims referencing a duplicated page must be blocked.
    """

    reference_counts = Counter(
        get_page_reference(claim)
        for claim in claims
    )

    return {
        reference
        for reference, count in reference_counts.items()
        if count > 1
    }


def map_local_evidence_status(
    evidence_status: str,
) -> FinalStatus:
    """
    Convert local PDF and OCR preparation statuses
    into final reimbursement statuses.
    """

    status_map: dict[str, FinalStatus] = {
        "PDF_MISSING": "PDF_MISSING",
        "PAGE_MISSING": "PAGE_MISSING",
        "TEXT_NOT_FOUND": "OCR_UNCLEAR",
    }

    return status_map.get(
        evidence_status,
        "POSSIBLE_MATCH_NOT_APPROVED",
    )


def process_monthly_worksheet(
    excel_path: str | Path,
    worksheet_name: str,
    pdf_directory: str | Path,
) -> WorksheetProcessingResult:
    """
    Process every valid reimbursement claim in one worksheet.

    There is no fixed claim limit and no PDF page limit.

    Only the PDF pages referenced by valid claims are rendered,
    OCR-processed, analyzed and verified.

    Duplicate page references are blocked before OCR or SDK
    processing, so no OpenAI credits are used for those claims.
    """

    # Import locally so duplicate-only and Excel-only tests do not
    # unnecessarily initialize EasyOCR, PyTorch, or PDF processing.
    from workflow.end_to_end_workflow import (
        process_claim_from_files,
    )

    claims, excel_errors = read_claims_from_worksheet(
        file_path=excel_path,
        worksheet_name=worksheet_name,
    )

    duplicate_references = (
        find_duplicate_page_references(
            claims
        )
    )

    results: list[WorksheetClaimResult] = []

    for claim in claims:
        page_reference = get_page_reference(
            claim
        )

        if page_reference in duplicate_references:
            results.append(
                WorksheetClaimResult(
                    claim=claim,
                    result_source="local_validation",
                    final_status=(
                        "DUPLICATE_PAGE_REFERENCE"
                    ),
                    auto_payable=False,
                    message=(
                        "The same monthly PDF page is referenced "
                        "by multiple claims. No OCR or OpenAI SDK "
                        "analysis was performed."
                    ),
                    workflow_result=None,
                )
            )
            continue

        workflow_result = process_claim_from_files(
            claim=claim,
            pdf_directory=pdf_directory,
        )

        if workflow_result.processing_result is None:
            final_status = map_local_evidence_status(
                workflow_result.evidence.status
            )

            results.append(
                WorksheetClaimResult(
                    claim=claim,
                    result_source="local_validation",
                    final_status=final_status,
                    auto_payable=False,
                    message=workflow_result.message,
                    workflow_result=workflow_result,
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
                    processing_result.result_source
                ),
                final_status=(
                    final_decision.final_status
                ),
                auto_payable=(
                    final_decision.auto_payable
                ),
                message=(
                    final_decision.reasons[0]
                ),
                workflow_result=workflow_result,
            )
        )

    approved_count = sum(
        1
        for result in results
        if result.auto_payable
    )

    exception_count = sum(
        1
        for result in results
        if not result.auto_payable
    )

    duplicate_page_claims = sum(
        1
        for result in results
        if result.final_status
        == "DUPLICATE_PAGE_REFERENCE"
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
        completed_claims=completed_claims,
        approved_count=approved_count,
        exception_count=exception_count,
        duplicate_page_claims=(
            duplicate_page_claims
        ),
        excel_errors=excel_errors,
        results=results,
    )