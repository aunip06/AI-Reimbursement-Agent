from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from models.receipt_candidate import (
    PageCandidateDetection,
    ReceiptCandidate,
)


RotationDegrees = Literal[
    0,
    90,
    180,
    270,
]


class CandidateReceiptEvidence(BaseModel):
    """
    OCR and PDF-text evidence for one independently
    detected receipt candidate.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    candidate: ReceiptCandidate

    selected_rotation_degrees: RotationDegrees

    tested_rotations: list[RotationDegrees]

    selected_image_path: str = Field(
        min_length=1
    )

    direct_pdf_text: str = ""

    ocr_text: str = ""

    combined_evidence_text: str = ""

    ocr_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    text_found: bool

    from_cache: bool

    message: str = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_text_state(self):
        if (
            self.text_found
            and not self.combined_evidence_text
        ):
            raise ValueError(
                "text_found=True requires evidence text."
            )

        if (
            not self.text_found
            and self.combined_evidence_text
        ):
            raise ValueError(
                "text_found=False requires empty evidence text."
            )

        return self


class PageReceiptCandidateEvidence(BaseModel):
    """
    Complete independent evidence for all detected
    receipt candidates on one PDF page.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    detection: PageCandidateDetection

    candidate_count: int = Field(
        ge=0
    )

    text_candidate_count: int = Field(
        ge=0
    )

    candidates: list[
        CandidateReceiptEvidence
    ]

    message: str = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_counts(self):
        if self.candidate_count != len(
            self.candidates
        ):
            raise ValueError(
                "candidate_count must equal "
                "the evidence candidate count."
            )

        actual_text_count = sum(
            candidate.text_found
            for candidate in self.candidates
        )

        if (
            self.text_candidate_count
            != actual_text_count
        ):
            raise ValueError(
                "text_candidate_count is incorrect."
            )

        if (
            self.detection.blank_page
            and self.candidates
        ):
            raise ValueError(
                "Blank pages cannot contain candidate evidence."
            )

        return self