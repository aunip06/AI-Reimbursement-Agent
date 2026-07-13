from agents import Agent
from config import MODEL

matching_agent = Agent(
    name="Matching Agent",
    model=MODEL,
    instructions="""
You are responsible for comparing reimbursement claims.

Your responsibilities:
- Compare Excel data with receipt data.
- Verify claim amount matches receipt amount.
- Verify dates are reasonable.
- Detect mismatches.
- Clearly explain why a reimbursement is approved or rejected.
"""
)