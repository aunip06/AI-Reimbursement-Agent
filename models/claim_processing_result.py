from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.final_decision import FinalDecision
from models.reimbursement_analysis import ReimbursementAnalysis


class ClaimProcessingResult(BaseModel):
    """
    Complete result for processing one reimbursement claim
    against OCR evidence from its referenced PDF page.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)

    result_source: Literal[
        "cache",
        "openai",
        "dry_run",
    ]

    analysis: ReimbursementAnalysis | None = None

    final_decision: FinalDecision | None = None

    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result_content(self):
        if self.result_source in {"cache", "openai"}:
            if self.analysis is None:
                raise ValueError(
                    "Completed processing requires an analysis result."
                )

            if self.final_decision is None:
                raise ValueError(
                    "Completed processing requires a final decision."
                )

        if self.result_source == "dry_run":
            if self.analysis is not None or self.final_decision is not None:
                raise ValueError(
                    "Dry-run results must not contain generated analysis."
                )

        return self