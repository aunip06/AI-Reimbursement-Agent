from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from models.final_decision import FinalDecision
from models.reimbursement_analysis import (
    ReimbursementAnalysis,
)


CandidateSelectionStatus = Literal[
    "UNIQUE_MATCH",
    "AMBIGUOUS_MATCH",
    "NO_MATCH",
    "NO_CANDIDATES",
    "BLANK_PAGE",
]


class CandidateEvaluation(BaseModel):
    """
    Claim-matching result for one independent receipt candidate.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    candidate_no: int = Field(ge=1)

    local_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    local_reasons: list[str]

    exact_transaction_id_found: bool

    exact_invoice_no_found: bool

    amount_text_found: bool

    date_text_found: bool

    shortlisted: bool

    analysis: ReimbursementAnalysis | None = None

    final_decision: FinalDecision | None = None

    semantic_score: float = Field(
        ge=0.0,
        le=200.0,
        default=0.0,
    )

    strict_match: bool = False


class PageCandidateSelectionResult(BaseModel):
    """
    Final candidate selection for one claim and one PDF page.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)

    pdf_file_name: str = Field(min_length=1)

    page_number: int = Field(ge=1)

    status: CandidateSelectionStatus

    selected_candidate_no: int | None = None

    candidate_evaluations: list[
        CandidateEvaluation
    ]

    reasons: list[str]

    @model_validator(mode="after")
    def validate_selection(self):
        if self.status == "UNIQUE_MATCH":
            if self.selected_candidate_no is None:
                raise ValueError(
                    "UNIQUE_MATCH requires a selected candidate."
                )

        elif self.selected_candidate_no is not None:
            raise ValueError(
                "Only UNIQUE_MATCH may contain "
                "selected_candidate_no."
            )

        return self