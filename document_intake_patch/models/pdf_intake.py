from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.document_ingestion import DocumentIngestionResult
from models.receipt import Receipt


PDFIntakeStatus = Literal[
    "EXTRACTED_READY",
    "REQUIRED_DATA_MISSING",
    "OCR_UNCLEAR",
    "NO_RECEIPT_FOUND",
    "EMPTY_PAGE",
    "DUPLICATE_RECEIPT",
    "EXTRACTION_FAILED",
]

PDFIntakeResultSource = Literal[
    "local_validation",
    "cache",
    "openai",
]


class PDFIntakeItem(BaseModel):
    """One page-level exception or one independently detected bill."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    generated_id: str = Field(min_length=1)
    source_file_name: str = Field(min_length=1)
    normalized_pdf_path: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    candidate_no: int | None = Field(default=None, ge=1)
    status: PDFIntakeStatus
    result_source: PDFIntakeResultSource
    receipt: Receipt | None = None
    candidate_image_path: str | None = None
    candidate_map_image_path: str | None = None
    ocr_text: str = ""
    candidate_fingerprint: str | None = None
    perceptual_hash: str | None = None
    duplicate_of_generated_id: str | None = None
    from_cache: bool = False
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_item(self):
        if self.status == "EMPTY_PAGE" and self.candidate_no is not None:
            raise ValueError("EMPTY_PAGE must not contain a candidate number.")

        if self.status == "DUPLICATE_RECEIPT" and not self.duplicate_of_generated_id:
            raise ValueError(
                "DUPLICATE_RECEIPT requires duplicate_of_generated_id."
            )

        return self


class PDFIntakeResult(BaseModel):
    """Complete document-only receipt-intake result."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ingestion: DocumentIngestionResult
    total_pages: int = Field(ge=0)
    total_candidates: int = Field(ge=0)
    extracted_count: int = Field(ge=0)
    exception_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    items: list[PDFIntakeItem]
    report_path: str | None = None
    json_path: str | None = None
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_counts(self):
        actual_candidates = sum(item.candidate_no is not None for item in self.items)
        actual_extracted = sum(
            item.status == "EXTRACTED_READY" for item in self.items
        )
        actual_duplicates = sum(
            item.status == "DUPLICATE_RECEIPT" for item in self.items
        )

        if actual_candidates != self.total_candidates:
            raise ValueError("total_candidates does not match the result items.")

        if actual_extracted != self.extracted_count:
            raise ValueError("extracted_count does not match the result items.")

        if actual_duplicates != self.duplicate_count:
            raise ValueError("duplicate_count does not match the result items.")

        if self.exception_count != len(self.items) - self.extracted_count:
            raise ValueError("exception_count does not match the result items.")

        return self
