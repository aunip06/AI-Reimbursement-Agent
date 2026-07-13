from agents import Agent
from config import MODEL

excel_agent = Agent(
    name="Excel Agent",
    model=MODEL,
    instructions="""
You are responsible for understanding reimbursement Excel files.

Your responsibilities:
- Read reimbursement data.
- Identify employees.
- Extract claim amounts.
- Extract dates and reimbursement categories.
- Return structured information.
"""
)