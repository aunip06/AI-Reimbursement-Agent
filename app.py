from tools.pdf_tool import pdf_to_images
from tools.ocr_tool import extract_text
from agents.agents.parser_agent import parse_receipt

pdf_file = "input/exp_may.pdf"

print("Converting PDF to image...")

images = pdf_to_images(pdf_file)

print(f"Found {len(images)} page(s).\n")

for image in images:

    print(f"Reading: {image}")

    text = extract_text(image)

    print("\n========== OCR TEXT ==========\n")
    print(text)

    print("\n========== AI PARSED DATA ==========\n")

    data = parse_receipt(text)

    print(data)
    print(type(data))
print(data)