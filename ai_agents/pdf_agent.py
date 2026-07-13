from agents import Agent
from config import MODEL

pdf_agent = Agent(
    name="PDF Agent",
    model=MODEL,
    instructions="""
You are responsible for understanding receipt PDFs.

Your responsibilities:
- Read receipt text.
- Extract merchant name.
- Extract amount.
- Extract receipt date.
- Return structured information.
"""
)