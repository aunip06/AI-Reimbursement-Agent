import easyocr

# Create the OCR reader once
reader = easyocr.Reader(['en'])

def extract_text(image_path):
    """
    Extract text from an image using OCR.
    """
    results = reader.readtext(image_path, detail=0)

    return "\n".join(results)