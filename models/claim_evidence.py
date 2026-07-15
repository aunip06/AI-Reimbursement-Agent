from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


EvidenceStatus = Literal[
    "READY",
    "PDF_MISSING",
    "PAGE_MISSING",
    "TEXT_NOT_FOUND",
]


class ClaimEvidence(BaseModel):
    """
    Local evidence prepared from the exact PDF page
    referenced by one Excel reimbursement claim.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)

    pdf_file_name: str = Field(min_length=1)

    page_number: int = Field(ge=1)

    status: EvidenceStatus

    pdf_exists: bool

    page_exists: bool

    image_path: str | None = None

    direct_pdf_text: str = ""

    ocr_text: str = ""

    combined_evidence_text: str = ""

    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ready_evidence(self):
        if self.status == "READY":
            if not self.pdf_exists:
                raise ValueError(
                    "READY evidence requires pdf_exists=True."
                )

            if not self.page_exists:
                raise ValueError(
                    "READY evidence requires page_exists=True."
                )

            if not self.image_path:
                raise ValueError(
                    "READY evidence requires an image path."
                )

            if not self.combined_evidence_text:
                raise ValueError(
                    "READY evidence requires extracted text."
                )

        return self