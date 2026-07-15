from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from models.receipt import Receipt


VerificationStatus = Literal[
    "OK_AUTO_APPROVED",
    "BILL_NOT_FOUND_ON_PAGE",
    "OCR_UNCLEAR",
    "AMOUNT_MISMATCH",
    "DATE_MISMATCH",
    "VENDOR_MISMATCH",
    "TRANSACTION_ID_MISMATCH",
    "INVOICE_NO_MISMATCH",
    "POSSIBLE_MATCH_NOT_APPROVED",
]


class ReimbursementAnalysis(BaseModel):
    """
    Combined receipt extraction and claim-verification result
    produced by one OpenAI Agents SDK run.

    This is an agent recommendation. A final Python safety gate
    will decide whether auto_payable can become True.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(
        min_length=1,
        description="Expense_ID received from the Excel claim.",
    )

    receipt: Receipt = Field(
        description="Structured evidence extracted from the OCR text.",
    )

    amount_match: bool | None = Field(
        description=(
            "True when claimed and extracted amounts match exactly. "
            "Null when the comparison cannot be completed."
        )
    )

    date_match: bool | None = Field(
        description=(
            "True when claimed and extracted dates match exactly. "
            "Null when the comparison cannot be completed."
        )
    )

    vendor_match: bool | None = Field(
        description=(
            "True when the claimed vendor and extracted merchant "
            "represent the same business or payee."
        )
    )

    description_supported: bool | None = Field(
        description=(
            "True when the receipt evidence reasonably supports "
            "the claim description and expense category."
        )
    )

    payment_mode_match: bool | None = Field(
        description=(
            "True when claimed and extracted payment modes agree. "
            "Null when the receipt does not clearly show a payment mode."
        )
    )

    transaction_id_match: bool | None = Field(
        description=(
            "Exact transaction-ID or UTR comparison. "
            "Null when the claim does not require an ID."
        )
    )

    invoice_no_match: bool | None = Field(
        description=(
            "Exact invoice-number comparison. "
            "Null when the Excel claim does not provide an invoice number."
        )
    )

    recommended_status: VerificationStatus = Field(
        description="Agent-recommended reimbursement verification status."
    )

    auto_approval_recommended: bool = Field(
        description=(
            "True only when all mandatory evidence is clear and matching. "
            "This is not the final auto_payable decision."
        )
    )

    analysis_confidence: Literal[
        "high",
        "medium",
        "low",
    ] = Field(
        description="Confidence in the complete comparison result."
    )

    reasons: list[str] = Field(
        min_length=1,
        description=(
            "Short evidence-based reasons supporting the recommendation."
        ),
    )

    ambiguity_notes: str | None = Field(
        description=(
            "Unclear, missing, conflicting, or unusual evidence. "
            "Null when no material ambiguity exists."
        )
    )

    @model_validator(mode="after")
    def validate_approval_recommendation(self):
        """
        Prevent internally inconsistent approval recommendations.
        """

        if self.auto_approval_recommended:
            approval_checks = [
                self.recommended_status == "OK_AUTO_APPROVED",
                self.receipt.bill_found,
                self.receipt.confidence == "high",
                self.analysis_confidence == "high",
                self.amount_match is True,
                self.date_match is True,
                self.vendor_match is True,
                self.transaction_id_match is not False,
                self.invoice_no_match is not False,
            ]

            if not all(approval_checks):
                raise ValueError(
                    "Auto-approval recommendation requires clear receipt "
                    "evidence and all mandatory comparisons to pass."
                )

        if (
            self.recommended_status == "OK_AUTO_APPROVED"
            and not self.auto_approval_recommended
        ):
            raise ValueError(
                "OK_AUTO_APPROVED requires "
                "auto_approval_recommended=True."
            )

        return self