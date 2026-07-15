from pathlib import Path

import fitz

from config import TEMP_FOLDER
from models.pdf_page import PDFPage


RENDER_SCALE = 3


def validate_pdf_path(
    pdf_path: str | Path,
) -> Path:
    """
    Validate and return a PDF path.
    """

    source_path = Path(pdf_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"PDF file does not exist: {source_path}"
        )

    if source_path.suffix.casefold() != ".pdf":
        raise ValueError(
            f"Expected a PDF file: {source_path}"
        )

    return source_path


def pdf_to_images(
    pdf_path: str | Path,
) -> list[PDFPage]:
    """
    Render every page of a PDF into an image.

    Retained for compatibility with the existing application.
    """

    source_path = validate_pdf_path(pdf_path)

    output_directory = (
        Path(TEMP_FOLDER)
        / source_path.stem
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    rendered_pages: list[PDFPage] = []

    document = fitz.open(source_path)

    try:
        for page_index in range(
            len(document)
        ):
            page_number = page_index + 1

            page = document.load_page(
                page_index
            )

            image_path = (
                output_directory
                / f"page_{page_number:04d}.png"
            )

            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(
                    RENDER_SCALE,
                    RENDER_SCALE,
                ),
                alpha=False,
            )

            pixmap.save(
                str(image_path)
            )

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


def render_pdf_page(
    pdf_path: str | Path,
    page_number: int,
) -> PDFPage:
    """
    Render only one required PDF page.

    page_number uses one-based numbering because Excel
    Receipt_Page_No is also one-based.
    """

    source_path = validate_pdf_path(
        pdf_path
    )

    if page_number < 1:
        raise ValueError(
            "PDF page number must be at least 1."
        )

    output_directory = (
        Path(TEMP_FOLDER)
        / source_path.stem
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = fitz.open(source_path)

    try:
        page_index = page_number - 1

        if page_index >= len(document):
            raise IndexError(
                f"PDF page {page_number} does not exist. "
                f"The PDF contains {len(document)} page(s)."
            )

        page = document.load_page(
            page_index
        )

        image_path = (
            output_directory
            / f"page_{page_number:04d}.png"
        )

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                RENDER_SCALE,
                RENDER_SCALE,
            ),
            alpha=False,
        )

        pixmap.save(
            str(image_path)
        )

    finally:
        document.close()

    return PDFPage(
        source_file=source_path.name,
        page_number=page_number,
        image_path=image_path,
    )


def extract_pdf_text(
    pdf_path: str | Path,
) -> str:
    """
    Extract selectable text from every PDF page.
    """

    source_path = validate_pdf_path(
        pdf_path
    )

    document = fitz.open(source_path)

    try:
        page_texts: list[str] = []

        for page in document:
            page_text = page.get_text(
                "text"
            ).strip()

            if page_text:
                page_texts.append(
                    page_text
                )

        return "\n\n".join(
            page_texts
        )

    finally:
        document.close()


def extract_pdf_page_text(
    pdf_path: str | Path,
    page_number: int,
) -> str:
    """
    Extract selectable text from one exact PDF page.
    """

    source_path = validate_pdf_path(
        pdf_path
    )

    if page_number < 1:
        raise ValueError(
            "PDF page number must be at least 1."
        )

    document = fitz.open(source_path)

    try:
        page_index = page_number - 1

        if page_index >= len(document):
            raise IndexError(
                f"PDF page {page_number} does not exist. "
                f"The PDF contains {len(document)} page(s)."
            )

        page = document.load_page(
            page_index
        )

        return page.get_text(
            "text"
        ).strip()

    finally:
        document.close()