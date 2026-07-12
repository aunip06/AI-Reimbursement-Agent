from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def parse_receipt(ocr_text):
    prompt = f"""
You are an AI receipt parser.

Extract the following fields from the OCR text.

Return ONLY valid JSON.

{{
    "date": "",
    "amount": "",
    "merchant": "",
    "payment_app": "",
    "transaction_id": "",
    "utr": "",
    "message": ""
}}

OCR TEXT:
{ocr_text}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    print("\n========== RAW AI RESPONSE ==========\n")
    print(response.output_text)

    return response.output_text