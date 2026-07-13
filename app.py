from tools.pdf_tool import pdf_to_images
from tools.ocr_tool import extract_text
from ai_agents.receipt_extraction_agent import extract_receipt_data
from config import MAX_PAGES

pdf_file = "input/exp_may.pdf"

print("Converting PDF to image...")
images = pdf_to_images(pdf_file)

if MAX_PAGES is not None:
    images = images[:MAX_PAGES]

print(f"Processing {len(images)} page(s).")

for image in images:
    print(f"\nReading: {image}")

    ocr_text = extract_text(image)

    print("\n========== OCR TEXT ==========\n")
    print(ocr_text)

    print("\n========== AI EXTRACTION ==========\n")

    receipt = extract_receipt_data(ocr_text)

    print(receipt.model_dump())