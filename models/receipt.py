from typing import Optional
from pydantic import BaseModel


class Receipt(BaseModel):
    receipt_type: Optional[str] = None

    payment_app: Optional[str] = None

    merchant: Optional[str] = None

    amount: Optional[float] = None

    date: Optional[str] = None

    message: Optional[str] = None

    utr: Optional[str] = None

    transaction_id: Optional[str] = None

    invoice_number: Optional[str] = None

    gst_number: Optional[str] = None

    currency: Optional[str] = "INR"