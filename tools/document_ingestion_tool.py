from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import fitz
from PIL import (
    Image,
    ImageOps,
    ImageSequence,
)

from config import TEMP_FOLDER
from models.document_ingestion import (
    DocumentFamily,
    DocumentIngestionResult,
)


MAX_INPUT_FILE_BYTES = (
    100 * 1024 * 1024
)

WORD_EXTENSIONS = {
    ".doc",
    ".docx",
    ".docm",
    ".dot",
    ".dotx",
    ".dotm",
    ".rtf",
    ".txt",
    ".odt",
    ".html",
    ".htm",
}

PRESENTATION_EXTENSIONS = {
    ".ppt",
    ".pptx",
    ".pptm",
    ".pps",
    ".ppsx",
    ".ppsm",
    ".odp",
}

SPREADSHEET_EXTENSIONS = {
    ".xls",
    ".xlsx",
    ".xlsm",
    ".xlsb",
    ".csv",
    ".ods",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
    ".webp",
}

DIRECT_DOCUMENT_EXTENSIONS = {
    ".xps",
    ".epub",
    ".mobi",
    ".fb2",
    ".cbz",
    ".svg",
}


def calculate_file_fingerprint(
    file_path: str | Path,
) -> str:
    """
    Calculate a SHA-256 fingerprint without loading the
    entire file into memory.
    """

    source_path = Path(
        file_path
    )

    digest = hashlib.sha256()

    with source_path.open(
        "rb"
    ) as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def detect_document_family(
    source_path: str | Path,
) -> DocumentFamily:
    """
    Determine which conversion adapter should handle the file.
    """

    suffix = Path(
        source_path
    ).suffix.casefold()

    if suffix == ".pdf":
        return "pdf"

    if suffix in WORD_EXTENSIONS:
        return "word"

    if suffix in PRESENTATION_EXTENSIONS:
        return "presentation"

    if suffix in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"

    if suffix in IMAGE_EXTENSIONS:
        return "image"

    if suffix in DIRECT_DOCUMENT_EXTENSIONS:
        return "direct_document"

    return "unknown"


def build_output_directory(
    source_path: Path,
    document_fingerprint: str,
    output_directory: str | Path | None,
) -> Path:
    """
    Build a stable isolated conversion directory.
    """

    if output_directory is None:
        root_directory = (
            Path(TEMP_FOLDER)
            / "document_ingestion"
        )

    else:
        root_directory = Path(
            output_directory
        )

    safe_stem = "".join(
        character
        if (
            character.isalnum()
            or character in {
                "-",
                "_",
            }
        )
        else "_"
        for character in source_path.stem
    ).strip("_")

    if not safe_stem:
        safe_stem = "document"

    final_directory = (
        root_directory
        / (
            f"{safe_stem}_"
            f"{document_fingerprint[:12]}"
        )
    )

    final_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return final_directory


def validate_normalized_pdf(
    pdf_path: str | Path,
) -> tuple[int, bool]:
    """
    Return page count and password-protection state.
    """

    document = fitz.open(
        str(pdf_path)
    )

    try:
        password_protected = bool(
            document.needs_pass
        )

        if password_protected:
            return (
                0,
                True,
            )

        return (
            document.page_count,
            False,
        )

    finally:
        document.close()


def copy_pdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Copy an existing PDF into the canonical working directory.
    """

    shutil.copy2(
        source_path,
        output_pdf_path,
    )


def convert_direct_document_with_pymupdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Convert a document format supported directly by PyMuPDF.
    """

    source_document = fitz.open(
        str(source_path)
    )

    try:
        if source_document.needs_pass:
            raise PermissionError(
                "The document is password protected."
            )

        pdf_bytes = (
            source_document
            .convert_to_pdf()
        )

    finally:
        source_document.close()

    output_document = fitz.open(
        "pdf",
        pdf_bytes,
    )

    try:
        output_document.save(
            str(output_pdf_path)
        )

    finally:
        output_document.close()


def prepare_pillow_page(
    image: Image.Image,
) -> Image.Image:
    """
    Convert one image frame to a PDF-compatible RGB page.
    """

    corrected = ImageOps.exif_transpose(
        image.copy()
    )

    if corrected.mode in {
        "RGBA",
        "LA",
    }:
        rgba_image = corrected.convert(
            "RGBA"
        )

        background = Image.new(
            "RGB",
            rgba_image.size,
            "white",
        )

        background.paste(
            rgba_image,
            mask=rgba_image.getchannel(
                "A"
            ),
        )

        return background

    if (
        corrected.mode == "P"
        and "transparency"
        in corrected.info
    ):
        rgba_image = corrected.convert(
            "RGBA"
        )

        background = Image.new(
            "RGB",
            rgba_image.size,
            "white",
        )

        background.paste(
            rgba_image,
            mask=rgba_image.getchannel(
                "A"
            ),
        )

        return background

    return corrected.convert(
        "RGB"
    )


def convert_image_to_pdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Convert a single image or a multi-frame image into PDF.
    """

    image = Image.open(
        source_path
    )

    try:
        pages = [
            prepare_pillow_page(
                frame
            )
            for frame
            in ImageSequence.Iterator(
                image
            )
        ]

        if not pages:
            raise ValueError(
                "The image contains no readable frames."
            )

        first_page = pages[0]

        additional_pages = pages[
            1:
        ]

        first_page.save(
            output_pdf_path,
            format="PDF",
            resolution=300.0,
            save_all=True,
            append_images=(
                additional_pages
            ),
        )

    finally:
        image.close()


def initialize_office_com():
    """
    Initialize COM for the current Python thread.
    """

    import pythoncom

    pythoncom.CoInitialize()

    return pythoncom


def convert_word_to_pdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Convert Word-compatible documents to PDF.

    Macro execution is disabled.
    """

    pythoncom = initialize_office_com()

    application = None
    document = None

    try:
        import win32com.client

        application = (
            win32com.client.DispatchEx(
                "Word.Application"
            )
        )

        application.Visible = False
        application.DisplayAlerts = 0

        try:
            application.AutomationSecurity = 3

        except Exception:
            pass

        document = (
            application.Documents.Open(
                FileName=str(
                    source_path.resolve()
                ),
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Visible=False,
                OpenAndRepair=True,
            )
        )

        document.ExportAsFixedFormat(
            OutputFileName=str(
                output_pdf_path.resolve()
            ),
            ExportFormat=17,
            OpenAfterExport=False,
            OptimizeFor=0,
            Range=0,
            Item=0,
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=0,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )

    finally:
        if document is not None:
            try:
                document.Close(
                    SaveChanges=False
                )

            except Exception:
                pass

        if application is not None:
            try:
                application.Quit()

            except Exception:
                pass

        pythoncom.CoUninitialize()


def convert_powerpoint_to_pdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Convert PowerPoint-compatible presentations to PDF.

    Macro execution is disabled.
    """

    pythoncom = initialize_office_com()

    application = None
    presentation = None

    try:
        import win32com.client

        application = (
            win32com.client.DispatchEx(
                "PowerPoint.Application"
            )
        )

        try:
            application.AutomationSecurity = 3

        except Exception:
            pass

        presentation = (
            application.Presentations.Open(
                FileName=str(
                    source_path.resolve()
                ),
                ReadOnly=True,
                Untitled=False,
                WithWindow=False,
            )
        )

        presentation.SaveAs(
            str(
                output_pdf_path.resolve()
            ),
            32,
        )

    finally:
        if presentation is not None:
            try:
                presentation.Close()

            except Exception:
                pass

        if application is not None:
            try:
                application.Quit()

            except Exception:
                pass

        pythoncom.CoUninitialize()


def convert_excel_to_pdf(
    source_path: Path,
    output_pdf_path: Path,
) -> None:
    """
    Convert Excel-compatible workbooks and CSV files to PDF.

    Macro execution is disabled.
    """

    pythoncom = initialize_office_com()

    application = None
    workbook = None

    try:
        import win32com.client

        application = (
            win32com.client.DispatchEx(
                "Excel.Application"
            )
        )

        application.Visible = False
        application.DisplayAlerts = False
        application.AskToUpdateLinks = False

        try:
            application.AutomationSecurity = 3

        except Exception:
            pass

        workbook = (
            application.Workbooks.Open(
                Filename=str(
                    source_path.resolve()
                ),
                UpdateLinks=0,
                ReadOnly=True,
                IgnoreReadOnlyRecommended=True,
                Notify=False,
                AddToMru=False,
            )
        )

        workbook.ExportAsFixedFormat(
            Type=0,
            Filename=str(
                output_pdf_path.resolve()
            ),
            Quality=0,
            IncludeDocProperties=True,
            IgnorePrintAreas=False,
            OpenAfterPublish=False,
        )

    finally:
        if workbook is not None:
            try:
                workbook.Close(
                    SaveChanges=False
                )

            except Exception:
                pass

        if application is not None:
            try:
                application.Quit()

            except Exception:
                pass

        pythoncom.CoUninitialize()


def create_failure_result(
    *,
    source_path: Path,
    source_family: DocumentFamily,
    status: str,
    message: str,
    document_fingerprint: str | None = None,
) -> DocumentIngestionResult:
    """
    Create a safe non-ready ingestion result.
    """

    return DocumentIngestionResult(
        source_file_name=(
            source_path.name
        ),
        source_path=str(
            source_path
        ),
        source_extension=(
            source_path.suffix.casefold()
        ),
        source_family=(
            source_family
        ),
        status=status,
        normalized_pdf_path=None,
        page_count=0,
        converted=False,
        converter=None,
        document_fingerprint=(
            document_fingerprint
        ),
        message=message,
    )


def normalize_document_to_pdf(
    source_file: str | Path,
    output_directory: str | Path | None = None,
) -> DocumentIngestionResult:
    """
    Convert one supported input file into canonical PDF form.

    Unsupported or damaged files return a structured failure
    instead of terminating a multi-file batch.
    """

    source_path = Path(
        source_file
    )

    source_family = (
        detect_document_family(
            source_path
        )
    )

    if not source_path.exists():
        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="FILE_NOT_FOUND",
            message=(
                "The input document was not found."
            ),
        )

    if not source_path.is_file():
        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="UNSUPPORTED_FORMAT",
            message=(
                "The supplied input is not a regular file."
            ),
        )

    file_size = source_path.stat().st_size

    if file_size > MAX_INPUT_FILE_BYTES:
        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="FILE_TOO_LARGE",
            message=(
                "The input exceeds the current 100 MB "
                "document-ingestion limit."
            ),
        )

    if source_family == "unknown":
        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="UNSUPPORTED_FORMAT",
            message=(
                f"Unsupported input extension: "
                f"{source_path.suffix or '[none]'}"
            ),
        )

    document_fingerprint = (
        calculate_file_fingerprint(
            source_path
        )
    )

    final_directory = (
        build_output_directory(
            source_path=source_path,
            document_fingerprint=(
                document_fingerprint
            ),
            output_directory=(
                output_directory
            ),
        )
    )

    output_pdf_path = (
        final_directory
        / (
            f"{source_path.stem}"
            "_normalized.pdf"
        )
    )

    converter_name: str

    try:
        if source_family == "pdf":
            copy_pdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "pdf_passthrough"
            )

        elif source_family == "word":
            convert_word_to_pdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "microsoft_word"
            )

        elif (
            source_family
            == "presentation"
        ):
            convert_powerpoint_to_pdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "microsoft_powerpoint"
            )

        elif (
            source_family
            == "spreadsheet"
        ):
            convert_excel_to_pdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "microsoft_excel"
            )

        elif source_family == "image":
            convert_image_to_pdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "pillow"
            )

        elif (
            source_family
            == "direct_document"
        ):
            convert_direct_document_with_pymupdf(
                source_path,
                output_pdf_path,
            )

            converter_name = (
                "pymupdf"
            )

        else:
            raise ValueError(
                "No converter was selected."
            )

        if not output_pdf_path.exists():
            raise FileNotFoundError(
                "The converter did not create a PDF."
            )

        (
            page_count,
            password_protected,
        ) = validate_normalized_pdf(
            output_pdf_path
        )

        if password_protected:
            output_pdf_path.unlink(
                missing_ok=True
            )

            return create_failure_result(
                source_path=source_path,
                source_family=source_family,
                status=(
                    "PASSWORD_PROTECTED"
                ),
                message=(
                    "The normalized document requires a password."
                ),
                document_fingerprint=(
                    document_fingerprint
                ),
            )

        if page_count < 1:
            output_pdf_path.unlink(
                missing_ok=True
            )

            return create_failure_result(
                source_path=source_path,
                source_family=source_family,
                status="EMPTY_DOCUMENT",
                message=(
                    "The document contains no pages."
                ),
                document_fingerprint=(
                    document_fingerprint
                ),
            )

        return DocumentIngestionResult(
            source_file_name=(
                source_path.name
            ),
            source_path=str(
                source_path
            ),
            source_extension=(
                source_path.suffix.casefold()
            ),
            source_family=(
                source_family
            ),
            status="READY",
            normalized_pdf_path=str(
                output_pdf_path
            ),
            page_count=page_count,
            converted=(
                source_family != "pdf"
            ),
            converter=converter_name,
            document_fingerprint=(
                document_fingerprint
            ),
            message=(
                f"Document normalized successfully "
                f"using {converter_name}. "
                f"Pages: {page_count}."
            ),
        )

    except PermissionError:
        output_pdf_path.unlink(
            missing_ok=True
        )

        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="PASSWORD_PROTECTED",
            message=(
                "The document is password protected "
                "or access was denied."
            ),
            document_fingerprint=(
                document_fingerprint
            ),
        )

    except Exception as error:
        output_pdf_path.unlink(
            missing_ok=True
        )

        return create_failure_result(
            source_path=source_path,
            source_family=source_family,
            status="CONVERSION_FAILED",
            message=(
                f"Document conversion failed: "
                f"{type(error).__name__}: {error}"
            ),
            document_fingerprint=(
                document_fingerprint
            ),
        )