import fitz


def extract_pdf_text(file_path):
    """
    Extract text from a PDF receipt.

    Args:
        file_path (str): Path to PDF.

    Returns:
        str
    """

    try:
        document = fitz.open(file_path)

        text = ""

        for page in document:
            text += page.get_text()

        document.close()

        return text

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""
