from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


DocumentFamily = Literal[
    "pdf",
    "word",
    "presentation",
    "spreadsheet",
    "image",
    "direct_document",
    "unknown",
]


IngestionStatus = Literal[
    "READY",
    "FILE_NOT_FOUND",
    "FILE_TOO_LARGE",
    "UNSUPPORTED_FORMAT",
    "PASSWORD_PROTECTED",
    "EMPTY_DOCUMENT",
    "CONVERSION_FAILED",
]


class DocumentIngestionResult(BaseModel):
    """
    Result of converting one supported input document into
    the canonical PDF format used by the receipt pipeline.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    source_file_name: str = Field(
        min_length=1
    )

    source_path: str = Field(
        min_length=1
    )

    source_extension: str

    source_family: DocumentFamily

    status: IngestionStatus

    normalized_pdf_path: str | None = None

    page_count: int = Field(
        default=0,
        ge=0,
    )

    converted: bool = False

    converter: str | None = None

    document_fingerprint: str | None = None

    message: str = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_ready_result(self):
        if self.status == "READY":
            if not self.normalized_pdf_path:
                raise ValueError(
                    "READY ingestion requires a normalized PDF path."
                )

            if self.page_count < 1:
                raise ValueError(
                    "READY ingestion requires at least one page."
                )

            if not self.document_fingerprint:
                raise ValueError(
                    "READY ingestion requires a document fingerprint."
                )

        else:
            if self.normalized_pdf_path is not None:
                raise ValueError(
                    "Failed ingestion must not expose a normalized PDF."
                )

        return self