from pathlib import Path
from typing import Any

from models.claim import Claim
from models.claim_evidence import ClaimEvidence
from tools.evidence_cache_tool import (
    load_cached_page_evidence,
    save_cached_page_evidence,
)
from tools.pdf_tool import (
    extract_pdf_page_text,
    render_pdf_page,
)


def normalize_evidence_text(
    text: str,
) -> str:
    """
    Remove empty lines and unnecessary surrounding spaces.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


def combine_page_text(
    direct_pdf_text: str,
    ocr_text: str,
) -> str:
    """
    Combine selectable PDF text and local OCR evidence.

    Duplicate content is not repeated when both sources
    produce the same normalized text.
    """

    normalized_direct_text = (
        normalize_evidence_text(
            direct_pdf_text
        )
    )

    normalized_ocr_text = (
        normalize_evidence_text(
            ocr_text
        )
    )

    if (
        normalized_direct_text
        and normalized_direct_text
        == normalized_ocr_text
    ):
        return normalized_ocr_text

    evidence_sections: list[str] = []

    if normalized_direct_text:
        evidence_sections.append(
            "DIRECT PDF TEXT:\n"
            + normalized_direct_text
        )

    if normalized_ocr_text:
        evidence_sections.append(
            "LOCAL OCR TEXT:\n"
            + normalized_ocr_text
        )

    return "\n\n".join(
        evidence_sections
    )


def build_claim_evidence_from_cache(
    claim: Claim,
    cached_data: dict[str, Any],
) -> ClaimEvidence:
    """
    Rebuild a claim-specific evidence result from the
    page-level evidence cache.
    """

    return ClaimEvidence(
        expense_id=claim.expense_id,
        pdf_file_name=(
            claim.monthly_pdf_name
        ),
        page_number=claim.receipt_page_no,
        status=cached_data["status"],
        pdf_exists=cached_data[
            "pdf_exists"
        ],
        page_exists=cached_data[
            "page_exists"
        ],
        image_path=cached_data[
            "image_path"
        ],
        direct_pdf_text=cached_data[
            "direct_pdf_text"
        ],
        ocr_text=cached_data[
            "ocr_text"
        ],
        combined_evidence_text=(
            cached_data[
                "combined_evidence_text"
            ]
        ),
        message=(
            cached_data["message"]
            + " Reused from the local page-evidence cache."
        ),
    )


def prepare_claim_evidence(
    claim: Claim,
    pdf_directory: str | Path,
) -> ClaimEvidence:
    """
    Prepare evidence from the exact PDF page referenced
    by one reimbursement claim.

    Cached page evidence is reused before loading EasyOCR.
    """

    pdf_path = (
        Path(pdf_directory)
        / claim.monthly_pdf_name
    )

    if not pdf_path.exists():
        return ClaimEvidence(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="PDF_MISSING",
            pdf_exists=False,
            page_exists=False,
            image_path=None,
            direct_pdf_text="",
            ocr_text="",
            combined_evidence_text="",
            message=(
                "The monthly PDF file referenced by "
                "the Excel claim was not found."
            ),
        )

    cached_data = (
        load_cached_page_evidence(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
        )
    )

    if cached_data is not None:
        return (
            build_claim_evidence_from_cache(
                claim=claim,
                cached_data=cached_data,
            )
        )

    try:
        rendered_page = render_pdf_page(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
        )

        direct_pdf_text = (
            extract_pdf_page_text(
                pdf_path=pdf_path,
                page_number=(
                    claim.receipt_page_no
                ),
            )
        )

    except IndexError as error:
        evidence = ClaimEvidence(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="PAGE_MISSING",
            pdf_exists=True,
            page_exists=False,
            image_path=None,
            direct_pdf_text="",
            ocr_text="",
            combined_evidence_text="",
            message=str(error),
        )

        save_cached_page_evidence(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
            evidence=evidence,
        )

        return evidence

    # EasyOCR is imported only after the evidence cache misses.
    # Cached runs therefore avoid loading PyTorch and EasyOCR.
    from tools.ocr_tool import extract_text

    ocr_text = extract_text(
        str(
            rendered_page.image_path
        )
    ).strip()

    combined_evidence_text = (
        combine_page_text(
            direct_pdf_text=(
                direct_pdf_text
            ),
            ocr_text=ocr_text,
        )
    )

    if not combined_evidence_text:
        evidence = ClaimEvidence(
            expense_id=claim.expense_id,
            pdf_file_name=(
                claim.monthly_pdf_name
            ),
            page_number=(
                claim.receipt_page_no
            ),
            status="TEXT_NOT_FOUND",
            pdf_exists=True,
            page_exists=True,
            image_path=str(
                rendered_page.image_path
            ),
            direct_pdf_text="",
            ocr_text="",
            combined_evidence_text="",
            message=(
                "The PDF page was rendered, but no selectable "
                "text or local OCR text was found."
            ),
        )

        save_cached_page_evidence(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
            evidence=evidence,
        )

        return evidence

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
        image_path=str(
            rendered_page.image_path
        ),
        direct_pdf_text=direct_pdf_text,
        ocr_text=ocr_text,
        combined_evidence_text=(
            combined_evidence_text
        ),
        message=(
            "The exact claim PDF page was rendered and "
            "local evidence was prepared successfully."
        ),
    )

    save_cached_page_evidence(
        pdf_path=pdf_path,
        page_number=(
            claim.receipt_page_no
        ),
        evidence=evidence,
    )

    return evidence