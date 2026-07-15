from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.claim import Claim
from models.end_to_end_result import EndToEndClaimResult
from models.final_decision import FinalStatus


class WorksheetClaimResult(BaseModel):
    """
    Final worksheet-level result for one reimbursement claim.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    claim: Claim

    result_source: Literal[
        "local_validation",
        "cache",
        "openai",
    ]

    final_status: FinalStatus

    auto_payable: bool

    message: str = Field(min_length=1)

    workflow_result: EndToEndClaimResult | None = None


class WorksheetProcessingResult(BaseModel):
    """
    Complete processing result for one monthly worksheet.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    worksheet_name: str = Field(min_length=1)

    total_claims: int = Field(ge=0)

    completed_claims: int = Field(ge=0)

    approved_count: int = Field(ge=0)

    exception_count: int = Field(ge=0)

    duplicate_page_claims: int = Field(ge=0)

    excel_errors: list[dict[str, Any]]

    results: list[WorksheetClaimResult]