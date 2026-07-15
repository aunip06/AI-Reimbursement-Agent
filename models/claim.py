from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


PaymentMode = Literal[
    "upi",
    "cash",
    "card",
    "wallet",
    "bank_transfer",
    "unknown",
]


class Claim(BaseModel):
    """
    One reimbursement claim read from an employee Excel worksheet.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expense_id: str = Field(min_length=1)
    employee_id: str = Field(min_length=1)
    employee_name: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    surname: str = Field(min_length=1)

    expense_date: date

    expense_category: str = Field(min_length=1)
    description: str = Field(min_length=1)

    claimed_amount: Decimal = Field(
        gt=0,
        decimal_places=2,
    )

    vendor: str = Field(min_length=1)

    payment_mode: PaymentMode

    transaction_id: str | None = None
    invoice_no: str | None = None

    monthly_pdf_name: str = Field(min_length=1)

    receipt_page_no: int = Field(ge=1)

    remarks: str | None = None

    worksheet_name: str = Field(min_length=1)

    source_row_number: int = Field(ge=2)

    @model_validator(mode="after")
    def validate_digital_payment(self):
        digital_modes = {
            "upi",
            "card",
            "wallet",
            "bank_transfer",
        }

        if (
            self.payment_mode in digital_modes
            and not self.transaction_id
        ):
            raise ValueError(
                "Transaction ID is required for digital payments."
            )

        return self