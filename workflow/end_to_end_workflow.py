from pathlib import Path

from models.claim import Claim
from models.end_to_end_result import EndToEndClaimResult
from workflow.claim_evidence_workflow import (
    prepare_claim_evidence,
)
from workflow.reimbursement_workflow import (
    process_claim_ocr,
)


def process_claim_from_files(
    claim: Claim,
    pdf_directory: str | Path,
    *,
    duplicate_page_reference: bool = False,
    dry_run: bool | None = None,
) -> EndToEndClaimResult:
    """
    Process one Excel claim using its mapped monthly PDF page.

    Workflow:
    1. Find the monthly PDF.
    2. Render the exact Receipt_Page_No.
    3. Extract local OCR and selectable PDF text.
    4. Check the claim-aware cache.
    5. Run the SDK analysis when required.
    6. Apply the final approval safety gate.
    """

    evidence = prepare_claim_evidence(
        claim=claim,
        pdf_directory=pdf_directory,
    )

    if evidence.status != "READY":
        return EndToEndClaimResult(
            claim=claim,
            evidence=evidence,
            processing_result=None,
            workflow_status="LOCAL_ERROR",
            message=evidence.message,
        )

    processing_result = process_claim_ocr(
        claim=claim,
        ocr_text=evidence.combined_evidence_text,
        pdf_exists=evidence.pdf_exists,
        page_exists=evidence.page_exists,
        duplicate_page_reference=duplicate_page_reference,
        dry_run=dry_run,
    )

    if processing_result.result_source == "dry_run":
        workflow_status = "DRY_RUN"
        message = (
            "Evidence preparation completed. The SDK call "
            "was skipped because dry-run mode was enabled."
        )
    else:
        workflow_status = "COMPLETED"
        message = (
            "The claim completed PDF mapping, OCR, SDK analysis "
            "and final safety validation."
        )

    return EndToEndClaimResult(
        claim=claim,
        evidence=evidence,
        processing_result=processing_result,
        workflow_status=workflow_status,
        message=message,
    )