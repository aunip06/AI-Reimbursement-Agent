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
    "EMPTY_PAGE",
    "BILL_NOT_FOUND_ON_PAGE",
    "AMBIGUOUS_RECEIPT_SELECTION",
]


class ClaimEvidence(BaseModel):
    """
    Local evidence selected for one reimbursement claim.

    A PDF page may contain multiple screenshots. Only the
    selected candidate's image and text are stored as the
    claim evidence.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(
        min_length=1
    )

    pdf_file_name: str = Field(
        min_length=1
    )

    page_number: int = Field(
        ge=1
    )

    status: EvidenceStatus

    pdf_exists: bool

    page_exists: bool

    image_path: str | None = None

    direct_pdf_text: str = ""

    ocr_text: str = ""

    combined_evidence_text: str = ""

    candidate_count: int = Field(
        default=0,
        ge=0,
    )

    selected_candidate_no: int | None = Field(
        default=None,
        ge=1,
    )

    selected_candidate_fingerprint: str | None = None

    candidate_selection_status: str | None = None

    candidate_image_paths: list[str] = Field(
        default_factory=list
    )

    annotated_page_image_path: str | None = None

    message: str = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.status == "PDF_MISSING":
            if self.pdf_exists:
                raise ValueError(
                    "PDF_MISSING requires pdf_exists=False."
                )

            if self.page_exists:
                raise ValueError(
                    "PDF_MISSING requires page_exists=False."
                )

            return self

        if self.status == "PAGE_MISSING":
            if not self.pdf_exists:
                raise ValueError(
                    "PAGE_MISSING requires pdf_exists=True."
                )

            if self.page_exists:
                raise ValueError(
                    "PAGE_MISSING requires page_exists=False."
                )

            return self

        if not self.pdf_exists:
            raise ValueError(
                "Existing-page evidence requires pdf_exists=True."
            )

        if not self.page_exists:
            raise ValueError(
                "Existing-page evidence requires page_exists=True."
            )

        if self.status == "READY":
            if not self.image_path:
                raise ValueError(
                    "READY evidence requires a selected image."
                )

            if not self.combined_evidence_text:
                raise ValueError(
                    "READY evidence requires extracted text."
                )

            if self.selected_candidate_no is None:
                raise ValueError(
                    "READY evidence requires a selected candidate."
                )

            if not self.selected_candidate_fingerprint:
                raise ValueError(
                    "READY evidence requires a candidate fingerprint."
                )

        if (
            self.selected_candidate_no is not None
            and not self.selected_candidate_fingerprint
        ):
            raise ValueError(
                "A selected candidate requires its fingerprint."
            )

        return self