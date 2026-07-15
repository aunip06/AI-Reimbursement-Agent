from pathlib import Path

import fitz

from config import TEMP_FOLDER
from models.pdf_page import PDFPage


def pdf_to_images(
    pdf_path: str | Path,
) -> list[PDFPage]:
    """
    Convert every PDF page into a PNG image.

    Images are stored inside a PDF-specific temporary folder.
    """

    source_path = Path(pdf_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {source_path}"
        )

    if source_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a PDF file: {source_path}"
        )

    output_directory = Path(TEMP_FOLDER) / source_path.stem

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    rendered_pages: list[PDFPage] = []

    document = fitz.open(source_path)

    try:
        for page_index in range(len(document)):
            page_number = page_index + 1
            page = document[page_index]

            image_path = (
                output_directory
                / f"page_{page_number:04d}.png"
            )

            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(3, 3),
                alpha=False,
            )

            pixmap.save(str(image_path))

            rendered_pages.append(
                PDFPage(
                    source_file=source_path.name,
                    page_number=page_number,
                    image_path=image_path,
                )
            )

    finally:
        document.close()

    return rendered_pages