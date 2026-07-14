from tools.pdf_tool import pdf_to_images
from tools.ocr_tool import extract_text
from tools.cache_tool import load_cached_result, save_cached_result
from ai_agents.receipt_extraction_agent import extract_receipt_data
from config import MAX_PAGES, DRY_RUN


pdf_file = "input/exp_may.pdf"

print("Converting PDF to image...")

images = pdf_to_images(pdf_file)

# Limit the number of pages during development.
if MAX_PAGES is not None:
    images = images[:MAX_PAGES]

print(f"Processing {len(images)} page(s).")


for image in images:
    print(f"\nReading: {image}")

    # Extract text locally using OCR.
    ocr_text = extract_text(image)

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

    # No cache exists and dry-run mode is disabled.
    print("\n========== AI EXTRACTION ==========\n")

    receipt = extract_receipt_data(ocr_text)

    receipt_data = receipt.model_dump(mode="json")

    cache_path = save_cached_result(
        ocr_text=ocr_text,
        result=receipt_data,
    )

    print(receipt_data)
    print(f"\nExtraction saved to cache: {cache_path}")