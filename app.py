from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    ModelBehaviorError,
    ModelRefusalError,
)

from ai_agents.receipt_extraction_agent import extract_receipt_data
from config import DRY_RUN, MAX_PAGES
from tools.cache_tool import load_cached_result, save_cached_result
from tools.ocr_tool import extract_text
from tools.pdf_tool import pdf_to_images


pdf_file = "input/exp_may.pdf"

print("Converting PDF to images...")

# pdf_to_images() now returns a list of PDFPage objects.
pages = pdf_to_images(pdf_file)

# Limit the number of pages during development.
if MAX_PAGES is not None:
    pages = pages[:MAX_PAGES]

print(f"Processing {len(pages)} page(s).")


for page in pages:
    print(
        f"\nReading: {page.source_file}, "
        f"page {page.page_number}"
    )

    # Extract text locally from the rendered page image.
    ocr_text = extract_text(
        str(page.image_path)
    )

    print("\n========== OCR TEXT ==========\n")
    print(ocr_text)

    # Always check the local cache first.
    cached_result = load_cached_result(ocr_text)

    if cached_result is not None:
        print("\n========== CACHED AI EXTRACTION ==========\n")
        print(cached_result)
        continue

    # When no cache exists, dry-run mode prevents an OpenAI call.
    if DRY_RUN:
        print(
            "\nDRY RUN: No cached result found. "
            "OpenAI extraction skipped."
        )
        continue

    print("\n========== AI EXTRACTION ==========\n")

    try:
        receipt = extract_receipt_data(ocr_text)

    except MaxTurnsExceeded:
        print(
            "EXTRACTION ERROR: The agent did not complete within "
            "the configured turn limit."
        )
        print("The result was not cached. Processing will continue.")
        continue

    except ModelRefusalError:
        print(
            "EXTRACTION ERROR: The model refused the extraction request."
        )
        print("The result was not cached. Processing will continue.")
        continue

    except ModelBehaviorError:
        print(
            "EXTRACTION ERROR: The model returned invalid or "
            "unexpected structured output."
        )
        print("The result was not cached. Processing will continue.")
        continue

    except AgentsException as error:
        print(
            "EXTRACTION ERROR: An OpenAI Agents SDK error occurred."
        )
        print(f"Error type: {type(error).__name__}")
        print("The result was not cached. Processing will continue.")
        continue

    except (ValueError, TypeError) as error:
        print(
            "EXTRACTION ERROR: Local extraction validation failed."
        )
        print(f"Error type: {type(error).__name__}")
        print("The result was not cached. Processing will continue.")
        continue

    except Exception as error:
        print(
            "EXTRACTION ERROR: An unexpected extraction error occurred."
        )
        print(f"Error type: {type(error).__name__}")
        print("The result was not cached. Processing will continue.")
        continue

    # Convert the validated Pydantic result into JSON-compatible data.
    receipt_data = receipt.model_dump(mode="json")

    # Cache only successful extraction results.
    cache_path = save_cached_result(
        ocr_text=ocr_text,
        result=receipt_data,
    )

    print(receipt_data)
    print(f"\nExtraction saved to cache: {cache_path}")