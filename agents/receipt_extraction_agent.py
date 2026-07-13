from openai import OpenAI

from config import OPENAI_API_KEY, MODEL
from models.receipt import Receipt
from prompts.receipt_prompt import RECEIPT_PROMPT

client = OpenAI(api_key=OPENAI_API_KEY)


def extract_receipt_data(ocr_text: str) -> Receipt:
    """
    Uses GPT to extract structured information from OCR text.
    Returns a validated Receipt object.
    """

    response = client.responses.parse(
        model=MODEL,
        input=f"{RECEIPT_PROMPT}\n\nReceipt Text:\n{ocr_text}",
        text_format=Receipt,
    )

    return response.output_parsed