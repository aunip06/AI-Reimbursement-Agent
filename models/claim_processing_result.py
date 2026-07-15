from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.final_decision import FinalDecision
from models.reimbursement_analysis import ReimbursementAnalysis


class ClaimProcessingResult(BaseModel):
    """
    Complete SDK and safety-gate result for one claim.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)

    result_source: Literal[
        "cache",
        "openai",
    ]

    analysis: ReimbursementAnalysis

    final_decision: FinalDecision

    message: str = Field(min_length=1)