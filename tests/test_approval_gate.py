from models.claim import Claim
from models.receipt import Receipt
from models.reimbursement_analysis import ReimbursementAnalysis
from tools.approval_tool import apply_approval_safety_gate


claim = Claim(
    expense_id="EMP001_2026_05_001",
    employee_id="EMP001",
    employee_name="Amit Patil",
    first_name="Amit",
    surname="Patil",
    expense_date="2026-05-17",
    expense_category="Printing",
    description="Flyer printing",
    claimed_amount="360.00",
    vendor="Pratik PCMC",
    payment_mode="upi",
    transaction_id="TXN123456",
    monthly_pdf_name="amit_patil_may_2026.pdf",
    receipt_page_no=1,
    worksheet_name="2026-05_May",
    source_row_number=2,
)


receipt = Receipt(
    bill_found=True,
    receipt_type="upi_screenshot",
    payment_app="Google Pay",
    merchant="Pratik PCMC",
    amount=360.00,
    date="2026-05-17",
    payment_mode="upi",
    message="Payment successful",
    utr="TXN123456",
    transaction_id="TXN123456",
    invoice_no=None,
    receipt_no=None,
    gst_number=None,
    currency="INR",
    confidence="high",
    extraction_notes="Receipt details are clearly readable.",
)


analysis = ReimbursementAnalysis(
    expense_id=claim.expense_id,
    receipt=receipt,
    amount_match=True,
    date_match=True,
    vendor_match=True,
    description_supported=True,
    payment_mode_match=True,
    transaction_id_match=True,
    invoice_no_match=None,
    recommended_status="OK_AUTO_APPROVED",
    auto_approval_recommended=True,
    analysis_confidence="high",
    reasons=[
        "Amount, date, vendor and transaction ID match."
    ],
    ambiguity_notes=None,
)


approved_decision = apply_approval_safety_gate(
    claim=claim,
    analysis=analysis,
)

assert approved_decision.auto_payable is True
assert approved_decision.final_status == "OK_AUTO_APPROVED"


mismatched_receipt = receipt.model_copy(
    update={
        "amount": 500.00,
    }
)

mismatched_analysis = analysis.model_copy(
    update={
        "receipt": mismatched_receipt,
    }
)

mismatch_decision = apply_approval_safety_gate(
    claim=claim,
    analysis=mismatched_analysis,
)

assert mismatch_decision.auto_payable is False
assert mismatch_decision.final_status == "AMOUNT_MISMATCH"


print("Approval safety gate tests passed.")