import re


def parse_receipt(text):
    """
    Extract structured information from OCR text.
    """

    data = {
        "dates": [],
        "amounts": [],
        "utrs": [],
        "transaction_ids": []
    }

    # Dates like: 17 May 2026
    data["dates"] = re.findall(
        r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}",
        text
    )

    # Amounts like ₹360 or 360
    amounts = re.findall(r"₹?\s?(\d+)", text)

    data["amounts"] = amounts

    # UTR Numbers
    data["utrs"] = re.findall(
        r"UTR[:\s]+(\d+)",
        text
    )

    # PhonePe Transaction IDs
    data["transaction_ids"] = re.findall(
        r"T\d{20,}",
        text
    )

    return data