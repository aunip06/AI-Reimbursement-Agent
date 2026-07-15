from models.claim import Claim
from workflow.worksheet_workflow import (
    find_duplicate_page_references,
    get_page_reference,
)


def make_claim(
    expense_id: str,
    page_number: int,
) -> Claim:
    return Claim(
        expense_id=expense_id,
        employee_id="EMP001",
        employee_name="Demo User",
        first_name="Demo",
        surname="User",
        expense_date="2026-05-17",
        expense_category="Printing",
        description="Printing expense",
        claimed_amount="360.00",
        vendor="Demo Vendor",
        payment_mode="upi",
        transaction_id=f"TXN-{expense_id}",
        invoice_no=None,
        monthly_pdf_name="demo_user_may_2026.pdf",
        receipt_page_no=page_number,
        remarks=None,
        worksheet_name="2026-05_May",
        source_row_number=2,
    )


claim_1 = make_claim(
    expense_id="EXP001",
    page_number=1,
)

claim_2 = make_claim(
    expense_id="EXP002",
    page_number=1,
)

claim_3 = make_claim(
    expense_id="EXP003",
    page_number=2,
)


duplicates = find_duplicate_page_references(
    [
        claim_1,
        claim_2,
        claim_3,
    ]
)


assert get_page_reference(claim_1) in duplicates
assert get_page_reference(claim_2) in duplicates
assert get_page_reference(claim_3) not in duplicates
assert len(duplicates) == 1