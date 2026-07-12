from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Create OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def parse_receipt(ocr_text):
    """
    Extract structured receipt information from OCR text using GPT.
    """

    system_prompt = """
You are an AI Receipt Extraction Agent.

You will receive OCR text extracted from a payment receipt.

The receipt may belong to:
- PhonePe
- Google Pay
- Paytm
- Uber
- Hotel
- Restaurant
- Amazon
- Flight
- Any payment receipt

Extract ONLY the following fields.

Return ONLY valid JSON.

{
    "date": "",
    "amount": "",
    "merchant": "",
    "payment_app": "",
    "transaction_id": "",
    "utr": "",
    "message": ""
}

Rules:
- Do NOT explain anything.
- Do NOT add markdown.
- Do NOT wrap the JSON inside ```json.
- If a field is missing, leave it as an empty string.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": ocr_text,
            },
        ],
    )

    text = response.output_text.strip()

    # Safety cleanup (just in case the model still adds markdown)
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    print("\n========== AI RESPONSE ==========\n")
    print(text)

    return json.loads(text)