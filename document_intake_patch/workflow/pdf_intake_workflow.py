from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from ai_agents.receipt_extraction_agent import extract_receipt_data
from models.pdf_intake import PDFIntakeItem, PDFIntakeResult
from models.receipt import Receipt
from tools.cache_tool import load_cached_result, save_cached_result
from tools.document_ingestion_tool import normalize_document_to_pdf
from tools.pdf_intake_report_tool import write_pdf_intake_report
from tools.pdf_tool import render_pdf_page
from workflow.receipt_candidate_evidence_workflow import (
    prepare_page_candidate_evidence,
)


def safe_file_stem(value: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe_value or "document"


def normalize_identifier(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"[^a-z0-9]", "", value.casefold())


def calculate_perceptual_hash(image_path: str | Path) -> str | None:
    """Calculate a compact difference hash for duplicate detection."""

    path = Path(image_path)

    if not path.exists():
        return None

    try:
        with Image.open(path) as image:
            grayscale = image.convert("L").resize((9, 8))
            pixels = list(grayscale.getdata())

    except Exception:
        return None

    bits: list[int] = []

    for row in range(8):
        row_start = row * 9

        for column in range(8):
            left_value = pixels[row_start + column]
            right_value = pixels[row_start + column + 1]
            bits.append(int(left_value > right_value))

    hash_value = 0

    for bit in bits:
        hash_value = (hash_value << 1) | bit

    return f"{hash_value:016x}"


def load_or_extract_receipt(
    ocr_text: str,
) -> tuple[Receipt, str, bool]:
    """Return the receipt, result source, and cache flag."""

    cached_result = load_cached_result(ocr_text)

    if cached_result is not None:
        try:
            receipt = Receipt.model_validate(cached_result)

        except ValidationError:
            receipt = None

        else:
            return receipt, "cache", True

    receipt = extract_receipt_data(ocr_text)

    save_cached_result(
        ocr_text=ocr_text,
        result=receipt.model_dump(mode="json"),
    )

    return receipt, "openai", False


def classify_receipt(receipt: Receipt) -> tuple[str, str]:
    """Classify extraction completeness without approving payment."""

    if not receipt.bill_found:
        return (
            "NO_RECEIPT_FOUND",
            "The isolated candidate does not contain valid financial evidence.",
        )

    if receipt.confidence == "low":
        return (
            "OCR_UNCLEAR",
            "A bill was detected, but the extracted evidence has low confidence.",
        )

    missing_fields = [
        field_name
        for field_name, field_value in {
            "date": receipt.date,
            "amount": receipt.amount,
            "remark": getattr(receipt, "remark", None),
        }.items()
        if field_value is None
        or (isinstance(field_value, str) and not field_value.strip())
    ]

    if missing_fields:
        return (
            "REQUIRED_DATA_MISSING",
            "The bill was extracted, but required intake fields are missing: "
            + ", ".join(missing_fields)
            + ".",
        )

    return (
        "EXTRACTED_READY",
        "Date, amount, and remark were extracted from this isolated bill candidate.",
    )


def build_duplicate_key(item: PDFIntakeItem) -> str | None:
    receipt = item.receipt

    if receipt is None or not receipt.bill_found:
        return None

    identifiers = [
        ("transaction_id", receipt.transaction_id),
        ("utr", receipt.utr),
        ("invoice_no", receipt.invoice_no),
        ("receipt_no", receipt.receipt_no),
    ]

    for identifier_name, value in identifiers:
        normalized_value = normalize_identifier(value)

        if len(normalized_value) >= 6:
            return f"{identifier_name}:{normalized_value}"

    if item.perceptual_hash:
        return "visual:" + item.perceptual_hash

    return None


def apply_duplicate_protection(
    items: list[PDFIntakeItem],
) -> list[PDFIntakeItem]:
    """Keep the first occurrence and mark later repeated receipts."""

    grouped_items: dict[str, list[PDFIntakeItem]] = defaultdict(list)

    for item in items:
        duplicate_key = build_duplicate_key(item)

        if duplicate_key:
            grouped_items[duplicate_key].append(item)

    duplicate_ids: dict[str, str] = {}

    for grouped_results in grouped_items.values():
        if len(grouped_results) < 2:
            continue

        ordered = sorted(
            grouped_results,
            key=lambda result: (
                result.page_number,
                result.candidate_no or 0,
                result.generated_id,
            ),
        )

        original_id = ordered[0].generated_id

        for duplicate_item in ordered[1:]:
            duplicate_ids[duplicate_item.generated_id] = original_id

    protected_items: list[PDFIntakeItem] = []

    for item in items:
        original_id = duplicate_ids.get(item.generated_id)

        if original_id is None:
            protected_items.append(item)
            continue

        protected_items.append(
            item.model_copy(
                deep=True,
                update={
                    "status": "DUPLICATE_RECEIPT",
                    "duplicate_of_generated_id": original_id,
                    "message": (
                        "This receipt duplicates "
                        f"{original_id}. It was not counted as a new intake record."
                    ),
                },
            )
        )

    return protected_items


def create_result_and_outputs(
    *,
    ingestion,
    total_pages: int,
    items: list[PDFIntakeItem],
    work_directory: Path,
    message: str,
) -> PDFIntakeResult:
    protected_items = apply_duplicate_protection(items)

    extracted_count = sum(
        item.status == "EXTRACTED_READY" for item in protected_items
    )

    duplicate_count = sum(
        item.status == "DUPLICATE_RECEIPT" for item in protected_items
    )

    total_candidates = sum(
        item.candidate_no is not None for item in protected_items
    )

    safe_stem = safe_file_stem(Path(ingestion.source_file_name).stem)
    report_path = work_directory / f"{safe_stem}_document_intake.xlsx"
    json_path = work_directory / f"{safe_stem}_document_intake.json"

    result = PDFIntakeResult(
        ingestion=ingestion,
        total_pages=total_pages,
        total_candidates=total_candidates,
        extracted_count=extracted_count,
        exception_count=len(protected_items) - extracted_count,
        duplicate_count=duplicate_count,
        items=protected_items,
        report_path=str(report_path),
        json_path=str(json_path),
        message=message,
    )

    work_directory.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )

    write_pdf_intake_report(
        result=result,
        report_path=report_path,
    )

    return result


def process_document_intake(
    source_file: str | Path,
    output_root: str | Path = "output/pdf_intake",
) -> PDFIntakeResult:
    """Normalize and process every bill candidate in one document."""

    source_path = Path(source_file)
    output_root_path = Path(output_root)

    ingestion = normalize_document_to_pdf(
        source_file=source_path,
        output_directory=output_root_path / "normalized",
    )

    fingerprint_part = (
        ingestion.document_fingerprint or "no_fingerprint"
    )[:12]

    work_directory = output_root_path / (
        safe_file_stem(source_path.stem) + "_" + fingerprint_part
    )

    if ingestion.status != "READY":
        return create_result_and_outputs(
            ingestion=ingestion,
            total_pages=0,
            items=[],
            work_directory=work_directory,
            message="Document intake could not start: " + ingestion.message,
        )

    normalized_pdf_path = Path(ingestion.normalized_pdf_path)
    items: list[PDFIntakeItem] = []

    for page_number in range(1, ingestion.page_count + 1):
        rendered_page = render_pdf_page(
            pdf_path=normalized_pdf_path,
            page_number=page_number,
        )

        page_output_directory = (
            work_directory / "evidence" / f"page_{page_number:04d}"
        )

        page_evidence = prepare_page_candidate_evidence(
            pdf_path=normalized_pdf_path,
            page_number=page_number,
            rendered_image_path=rendered_page.image_path,
            output_directory=page_output_directory,
        )

        candidate_map_path = page_evidence.detection.annotated_image_path

        if page_evidence.detection.blank_page:
            items.append(
                PDFIntakeItem(
                    generated_id=(
                        f"{safe_file_stem(source_path.stem)}-P{page_number:04d}"
                    ),
                    source_file_name=source_path.name,
                    normalized_pdf_path=str(normalized_pdf_path),
                    page_number=page_number,
                    candidate_no=None,
                    status="EMPTY_PAGE",
                    result_source="local_validation",
                    receipt=None,
                    candidate_image_path=None,
                    candidate_map_image_path=candidate_map_path,
                    ocr_text="",
                    candidate_fingerprint=None,
                    perceptual_hash=None,
                    duplicate_of_generated_id=None,
                    from_cache=False,
                    message="The page is visually blank.",
                )
            )
            continue

        if not page_evidence.candidates:
            items.append(
                PDFIntakeItem(
                    generated_id=(
                        f"{safe_file_stem(source_path.stem)}-P{page_number:04d}"
                    ),
                    source_file_name=source_path.name,
                    normalized_pdf_path=str(normalized_pdf_path),
                    page_number=page_number,
                    candidate_no=None,
                    status="NO_RECEIPT_FOUND",
                    result_source="local_validation",
                    receipt=None,
                    candidate_image_path=None,
                    candidate_map_image_path=candidate_map_path,
                    ocr_text="",
                    candidate_fingerprint=None,
                    perceptual_hash=None,
                    duplicate_of_generated_id=None,
                    from_cache=False,
                    message="No receipt candidate was detected on this page.",
                )
            )
            continue

        for candidate_evidence in page_evidence.candidates:
            candidate = candidate_evidence.candidate

            generated_id = (
                f"{safe_file_stem(source_path.stem)}"
                f"-P{page_number:04d}"
                f"-C{candidate.candidate_no:02d}"
            )

            perceptual_hash = calculate_perceptual_hash(
                candidate_evidence.selected_image_path
            )

            if not candidate_evidence.text_found:
                items.append(
                    PDFIntakeItem(
                        generated_id=generated_id,
                        source_file_name=source_path.name,
                        normalized_pdf_path=str(normalized_pdf_path),
                        page_number=page_number,
                        candidate_no=candidate.candidate_no,
                        status="OCR_UNCLEAR",
                        result_source="local_validation",
                        receipt=None,
                        candidate_image_path=candidate_evidence.selected_image_path,
                        candidate_map_image_path=candidate_map_path,
                        ocr_text="",
                        candidate_fingerprint=candidate.image_fingerprint,
                        perceptual_hash=perceptual_hash,
                        duplicate_of_generated_id=None,
                        from_cache=False,
                        message="No readable text was found in this candidate.",
                    )
                )
                continue

            try:
                receipt, result_source, from_cache = load_or_extract_receipt(
                    candidate_evidence.combined_evidence_text
                )

                status, message = classify_receipt(receipt)

                items.append(
                    PDFIntakeItem(
                        generated_id=generated_id,
                        source_file_name=source_path.name,
                        normalized_pdf_path=str(normalized_pdf_path),
                        page_number=page_number,
                        candidate_no=candidate.candidate_no,
                        status=status,
                        result_source=result_source,
                        receipt=receipt,
                        candidate_image_path=candidate_evidence.selected_image_path,
                        candidate_map_image_path=candidate_map_path,
                        ocr_text=candidate_evidence.combined_evidence_text,
                        candidate_fingerprint=candidate.image_fingerprint,
                        perceptual_hash=perceptual_hash,
                        duplicate_of_generated_id=None,
                        from_cache=from_cache,
                        message=message,
                    )
                )

            except Exception as error:
                items.append(
                    PDFIntakeItem(
                        generated_id=generated_id,
                        source_file_name=source_path.name,
                        normalized_pdf_path=str(normalized_pdf_path),
                        page_number=page_number,
                        candidate_no=candidate.candidate_no,
                        status="EXTRACTION_FAILED",
                        result_source="local_validation",
                        receipt=None,
                        candidate_image_path=candidate_evidence.selected_image_path,
                        candidate_map_image_path=candidate_map_path,
                        ocr_text=candidate_evidence.combined_evidence_text,
                        candidate_fingerprint=candidate.image_fingerprint,
                        perceptual_hash=perceptual_hash,
                        duplicate_of_generated_id=None,
                        from_cache=False,
                        message=(
                            "Receipt extraction failed: "
                            f"{type(error).__name__}: {error}"
                        ),
                    )
                )

    return create_result_and_outputs(
        ingestion=ingestion,
        total_pages=ingestion.page_count,
        items=items,
        work_directory=work_directory,
        message=(
            "Document-only intake completed. Results are extraction records, "
            "not reimbursement approvals."
        ),
    )
