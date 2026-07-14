from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Receipt(BaseModel):
    """
    Structured evidence extracted from one receipt or payment document.

    This model contains extraction evidence only.
    It does not approve or reject a reimbursement claim.
    """

    model_config = ConfigDict(extra="forbid")

    bill_found: bool = Field(
        description=(
            "True when the OCR text contains a receipt, invoice, bill, "
            "ticket, or payment confirmation."
        )
    )

    receipt_type: Literal[
        "upi_screenshot",
        "invoice",
        "receipt",
        "cash_bill",
        "card_statement",
        "travel_ticket",
        "hotel_bill",
        "unknown",
    ] = Field(
        description="The type of financial document."
    )

    payment_app: str | None = Field(
        description="Payment application name, such as GPay or PhonePe."
    )

    merchant: str | None = Field(
        description="Merchant, vendor, payee, hotel, airline, or service provider."
    )

    amount: float | None = Field(
        description="Final paid amount or final bill total."
    )

    date: str | None = Field(
        description="Bill or transaction date in YYYY-MM-DD format."
    )

    payment_mode: Literal[
        "upi",
        "cash",
        "card",
        "wallet",
        "bank_transfer",
        "unknown",
    ] = Field(
        description="Detected payment method."
    )

    message: str | None = Field(
        description="Important payment status or transaction message."
    )

    utr: str | None = Field(
        description="UPI or bank reference number."
    )

    transaction_id: str | None = Field(
        description="Transaction identifier shown on the document."
    )

    invoice_no: str | None = Field(
        description="Invoice number, when present."
    )

    receipt_no: str | None = Field(
        description="Receipt number, when present."
    )

    gst_number: str | None = Field(
        description="GST registration number, when present."
    )

    currency: str | None = Field(
        description="Currency code such as INR, USD, or EUR."
    )

    confidence: Literal[
        "high",
        "medium",
        "low",
    ] = Field(
        description="Confidence in the extracted information."
    )

    extraction_notes: str = Field(
        description=(
            "Short explanation of unclear, missing, conflicting, "
            "or unusual information."
        )
    )