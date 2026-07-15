from models.claim import Claim
from models.receipt import Receipt
from models.reimbursement_analysis import (
    ReimbursementAnalysis,
)
from tools.cache_tool import save_cached_analysis_result
from workflow.reimbursement_workflow import process_claim_ocr


ocr_text = """
Payment successful
Paid to Pratik PCMC
Amount INR 360.00
Date 17 May 2026
Transaction ID TXN123456
"""


claim = Claim(
    expense_id="EMP001_2026_05_WORKFLOW_TEST",
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
    invoice_no=None,
    monthly_pdf_name="amit_patil_may_2026.pdf",
    receipt_page_no=1,
    remarks=None,
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
    extraction_notes="Receipt evidence is clear.",
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


save_cached_analysis_result(
    claim=claim,
    ocr_text=ocr_text,
    result=analysis.model_dump(mode="json"),
)


workflow_result = process_claim_ocr(
    claim=claim,
    ocr_text=ocr_text,
)


assert workflow_result.result_source == "cache"

assert workflow_result.analysis is not None

assert workflow_result.final_decision is not None

assert workflow_result.final_decision.auto_payable is True

assert (
    workflow_result.final_decision.final_status
    == "OK_AUTO_APPROVED"
)


print("Reimbursement workflow cache test passed.")