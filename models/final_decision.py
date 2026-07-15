from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FinalStatus = Literal[
    "OK_AUTO_APPROVED",
    "PDF_MISSING",
    "PAGE_NOT_SPECIFIED",
    "PAGE_MISSING",
    "FORMAT_ERROR",
    "OCR_UNCLEAR",
    "BILL_NOT_FOUND_ON_PAGE",
    "AMOUNT_MISMATCH",
    "DATE_MISMATCH",
    "VENDOR_MISMATCH",
    "TRANSACTION_ID_MISMATCH",
    "INVOICE_NO_MISMATCH",
    "DUPLICATE_PAGE_REFERENCE",
    "EXTRA_BILL_PAGE_FOUND",
    "POSSIBLE_MATCH_NOT_APPROVED",
]


class FinalDecision(BaseModel):
    """
    Final reimbursement decision after applying the local
    non-overridable safety checks.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)

    agent_recommended_status: str = Field(
        min_length=1,
    )

    final_status: FinalStatus

    auto_payable: bool

    safety_checks: dict[str, bool]

    reasons: list[str] = Field(
        min_length=1,
    )