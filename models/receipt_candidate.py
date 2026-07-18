from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


CandidateSource = Literal[
    "native_pdf_image",
    "visual_region",
    "full_page_fallback",
]


class PixelBoundingBox(BaseModel):
    """
    Pixel coordinates of one detected receipt candidate.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    x_min: int = Field(ge=0)
    y_min: int = Field(ge=0)
    x_max: int = Field(gt=0)
    y_max: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dimensions(self):
        if self.x_max <= self.x_min:
            raise ValueError(
                "x_max must be greater than x_min."
            )

        if self.y_max <= self.y_min:
            raise ValueError(
                "y_max must be greater than y_min."
            )

        return self

    @property
    def width(self) -> int:
        return self.x_max - self.x_min

    @property
    def height(self) -> int:
        return self.y_max - self.y_min

    @property
    def area(self) -> int:
        return self.width * self.height


class ReceiptCandidate(BaseModel):
    """
    One independently detected screenshot or receipt region.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    candidate_no: int = Field(ge=1)

    page_number: int = Field(ge=1)

    source: CandidateSource

    bounding_box: PixelBoundingBox

    normalized_bounding_box: tuple[
        float,
        float,
        float,
        float,
    ]

    image_path: str = Field(min_length=1)

    area_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    detection_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    image_fingerprint: str = Field(
        min_length=16
    )

    notes: list[str] = Field(
        default_factory=list
    )


class PageCandidateDetection(BaseModel):
    """
    Complete candidate-detection result for one PDF page.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    pdf_file_name: str = Field(
        min_length=1
    )

    page_number: int = Field(ge=1)

    page_width: int = Field(gt=0)

    page_height: int = Field(gt=0)

    blank_page: bool

    non_white_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    edge_density: float = Field(
        ge=0.0,
        le=1.0,
    )

    candidate_count: int = Field(
        ge=0
    )

    candidates: list[ReceiptCandidate]

    annotated_image_path: str | None = None

    detector_version: str = Field(
        min_length=1
    )

    message: str = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_candidate_count(self):
        if self.candidate_count != len(
            self.candidates
        ):
            raise ValueError(
                "candidate_count must equal "
                "the number of candidates."
            )

        if self.blank_page and self.candidates:
            raise ValueError(
                "A blank page must not contain candidates."
            )

        return self