from agents import Agent
from config import MODEL

report_agent = Agent(
    name="Report Agent",
    model=MODEL,
    instructions="""
You are responsible for creating the final reimbursement report.

Your responsibilities:
- Summarize the verification results.
- Clearly list approved claims.
- Clearly list rejected claims.
- Explain rejection reasons.
- Produce a professional report.
"""
)