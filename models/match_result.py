from pydantic import BaseModel


class MatchResult(BaseModel):
    expense_no: int

    amount_match: bool
    date_match: bool
    description_match: bool

    status: str
    confidence: int
    reason: str