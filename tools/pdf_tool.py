import fitz
import os


def pdf_to_images(pdf_path, output_folder="temp"):
    """
    Convert PDF pages to PNG images using PyMuPDF.
    """

    os.makedirs(output_folder, exist_ok=True)

    pdf = fitz.open(pdf_path)

    image_paths = []

    for page_number in range(len(pdf)):
        page = pdf.load_page(page_number)

        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))

        image_path = os.path.join(
            output_folder,
            f"page_{page_number+1}.png"
        )

        pix.save(image_path)

        image_paths.append(image_path)

    pdf.close()

    return image_paths