from pathlib import Path

from models.claim import Claim
from models.claim_evidence import ClaimEvidence
from models.end_to_end_result import (
    EndToEndClaimResult,
)
from tools.evidence_cache_tool import (
    get_pdf_fingerprint,
)
from tools.pdf_tool import (
    render_pdf_page,
)
from workflow.candidate_selection_workflow import (
    select_candidate_for_claim,
)
from workflow.receipt_candidate_evidence_workflow import (
    prepare_page_candidate_evidence,
)
from workflow.reimbursement_workflow import (
    process_claim_ocr,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

CANDIDATE_TEMP_ROOT = (
    PROJECT_ROOT
    / "temp"
    / "candidate_claim_evidence"
)


def create_local_evidence_result(
    *,
    claim: Claim,
    status: str,
    message: str,
    pdf_exists: bool,
    page_exists: bool,
    image_path: str | None = None,
    candidate_count: int = 0,
    candidate_selection_status: str | None = None,
    candidate_image_paths: list[str] | None = None,
    annotated_page_image_path: str | None = None,
) -> EndToEndClaimResult:
    """
    Create a local non-payable workflow result.
    """

    evidence = ClaimEvidence(
        expense_id=claim.expense_id,
        pdf_file_name=(
            claim.monthly_pdf_name
        ),
        page_number=(
            claim.receipt_page_no
        ),
        status=status,
        pdf_exists=pdf_exists,
        page_exists=page_exists,
        image_path=image_path,
        direct_pdf_text="",
        ocr_text="",
        combined_evidence_text="",
        candidate_count=(
            candidate_count
        ),
        selected_candidate_no=None,
        selected_candidate_fingerprint=None,
        candidate_selection_status=(
            candidate_selection_status
        ),
        candidate_image_paths=(
            candidate_image_paths
            or []
        ),
        annotated_page_image_path=(
            annotated_page_image_path
        ),
        message=message,
    )

    return EndToEndClaimResult(
        claim=claim,
        evidence=evidence,
        processing_result=None,
        workflow_status="LOCAL_ERROR",
        message=message,
    )


def process_claim_from_files(
    claim: Claim,
    pdf_directory: str | Path,
    *,
    duplicate_page_reference: bool = False,
) -> EndToEndClaimResult:
    """
    Process one claim using isolated receipt candidates.

    Multiple screenshots on one page are detected, cropped,
    OCR-processed and evaluated independently.
    """

    pdf_path = (
        Path(pdf_directory)
        / claim.monthly_pdf_name
    )

    if not pdf_path.exists():
        return create_local_evidence_result(
            claim=claim,
            status="PDF_MISSING",
            message=(
                "The monthly PDF referenced by the "
                "Excel claim was not found."
            ),
            pdf_exists=False,
            page_exists=False,
        )

    try:
        rendered_page = render_pdf_page(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
        )

    except IndexError as error:
        return create_local_evidence_result(
            claim=claim,
            status="PAGE_MISSING",
            message=str(error),
            pdf_exists=True,
            page_exists=False,
        )

    pdf_fingerprint = (
        get_pdf_fingerprint(
            pdf_path
        )
    )

    page_output_directory = (
        CANDIDATE_TEMP_ROOT
        / pdf_fingerprint[:16]
        / (
            f"page_"
            f"{claim.receipt_page_no:04d}"
        )
    )

    page_evidence = (
        prepare_page_candidate_evidence(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
            rendered_image_path=(
                rendered_page.image_path
            ),
            output_directory=(
                page_output_directory
            ),
        )
    )

    candidate_image_paths = [
        candidate_evidence.selected_image_path
        for candidate_evidence
        in page_evidence.candidates
    ]

    selection = (
        select_candidate_for_claim(
            claim=claim,
            page_evidence=(
                page_evidence
            ),
        )
    )

    annotated_image_path = (
        page_evidence
        .detection
        .annotated_image_path
    )

    if selection.status == "BLANK_PAGE":
        return create_local_evidence_result(
            claim=claim,
            status="EMPTY_PAGE",
            message=(
                "The referenced PDF page is visually blank. "
                "No OCR or OpenAI payment analysis was performed."
            ),
            pdf_exists=True,
            page_exists=True,
            candidate_count=0,
            candidate_selection_status=(
                selection.status
            ),
            candidate_image_paths=[],
            annotated_page_image_path=(
                annotated_image_path
            ),
        )

    if selection.status == "NO_CANDIDATES":
        return create_local_evidence_result(
            claim=claim,
            status="BILL_NOT_FOUND_ON_PAGE",
            message=(
                "No readable receipt or payment screenshot "
                "was detected on the referenced PDF page."
            ),
            pdf_exists=True,
            page_exists=True,
            image_path=(
                annotated_image_path
            ),
            candidate_count=(
                page_evidence.candidate_count
            ),
            candidate_selection_status=(
                selection.status
            ),
            candidate_image_paths=(
                candidate_image_paths
            ),
            annotated_page_image_path=(
                annotated_image_path
            ),
        )

    if selection.status == "AMBIGUOUS_MATCH":
        return create_local_evidence_result(
            claim=claim,
            status=(
                "AMBIGUOUS_RECEIPT_SELECTION"
            ),
            message=(
                "Multiple isolated receipt candidates "
                "could correspond to this claim. "
                "Automatic payment was blocked."
            ),
            pdf_exists=True,
            page_exists=True,
            image_path=(
                annotated_image_path
            ),
            candidate_count=(
                page_evidence.candidate_count
            ),
            candidate_selection_status=(
                selection.status
            ),
            candidate_image_paths=(
                candidate_image_paths
            ),
            annotated_page_image_path=(
                annotated_image_path
            ),
        )

    if selection.status == "NO_MATCH":
        return create_local_evidence_result(
            claim=claim,
            status="BILL_NOT_FOUND_ON_PAGE",
            message=(
                "Receipt candidates were detected, but none "
                "could be uniquely associated with this claim."
            ),
            pdf_exists=True,
            page_exists=True,
            image_path=(
                annotated_image_path
            ),
            candidate_count=(
                page_evidence.candidate_count
            ),
            candidate_selection_status=(
                selection.status
            ),
            candidate_image_paths=(
                candidate_image_paths
            ),
            annotated_page_image_path=(
                annotated_image_path
            ),
        )

    selected_candidate_no = (
        selection.selected_candidate_no
    )

    selected_evidence = next(
        candidate_evidence
        for candidate_evidence
        in page_evidence.candidates
        if (
            candidate_evidence
            .candidate
            .candidate_no
            == selected_candidate_no
        )
    )

    selected_candidate = (
        selected_evidence.candidate
    )

    evidence = ClaimEvidence(
        expense_id=claim.expense_id,
        pdf_file_name=(
            claim.monthly_pdf_name
        ),
        page_number=(
            claim.receipt_page_no
        ),
        status="READY",
        pdf_exists=True,
        page_exists=True,
        image_path=(
            selected_evidence
            .selected_image_path
        ),
        direct_pdf_text=(
            selected_evidence
            .direct_pdf_text
        ),
        ocr_text=(
            selected_evidence
            .ocr_text
        ),
        combined_evidence_text=(
            selected_evidence
            .combined_evidence_text
        ),
        candidate_count=(
            page_evidence.candidate_count
        ),
        selected_candidate_no=(
            selected_candidate_no
        ),
        selected_candidate_fingerprint=(
            selected_candidate
            .image_fingerprint
        ),
        candidate_selection_status=(
            selection.status
        ),
        candidate_image_paths=(
            candidate_image_paths
        ),
        annotated_page_image_path=(
            annotated_image_path
        ),
        message=(
            f"Candidate {selected_candidate_no} was selected "
            f"from {page_evidence.candidate_count} independently "
            "detected receipt candidate(s)."
        ),
    )

    processing_result = (
        process_claim_ocr(
            claim=claim,
            ocr_text=(
                evidence
                .combined_evidence_text
            ),
            pdf_exists=True,
            page_exists=True,
            duplicate_page_reference=(
                duplicate_page_reference
            ),
        )
    )

    return EndToEndClaimResult(
        claim=claim,
        evidence=evidence,
        processing_result=(
            processing_result
        ),
        workflow_status="COMPLETED",
        message=(
            "The claim was matched to one isolated receipt "
            "candidate, analyzed and passed through the final "
            "deterministic safety gate."
        ),
    )