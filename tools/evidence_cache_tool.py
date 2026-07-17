from __future__ import annotations

import hashlib
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from models.claim_evidence import ClaimEvidence


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CACHE_ROOT = (
    PROJECT_ROOT
    / "cache"
    / "page_evidence"
)

RECORDS_DIRECTORY = (
    CACHE_ROOT
    / "records"
)

IMAGES_DIRECTORY = (
    CACHE_ROOT
    / "images"
)

EVIDENCE_CACHE_VERSION = "page-evidence-v1"
OCR_PIPELINE_VERSION = "easyocr-default-v1"
PDF_PIPELINE_VERSION = "pymupdf-render-v1"


@lru_cache(maxsize=256)
def calculate_pdf_sha256(
    resolved_path: str,
    file_size: int,
    modified_time_ns: int,
) -> str:
    """
    Calculate a PDF SHA-256 hash.

    The file size and modification time are part of the
    in-memory cache key, so the PDF is hashed only once
    during one application run unless the file changes.
    """

    del file_size
    del modified_time_ns

    digest = hashlib.sha256()

    with open(
        resolved_path,
        "rb",
    ) as pdf_file:
        while True:
            chunk = pdf_file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def get_pdf_fingerprint(
    pdf_path: str | Path,
) -> str:
    """
    Return a content fingerprint for one PDF.
    """

    resolved_path = Path(
        pdf_path
    ).resolve()

    file_stat = resolved_path.stat()

    return calculate_pdf_sha256(
        str(resolved_path),
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )


def build_page_cache_identity(
    pdf_path: str | Path,
    page_number: int,
) -> tuple[str, str]:
    """
    Build a stable page-evidence cache key.

    The cache automatically changes when:

    - PDF content changes
    - Page number changes
    - OCR pipeline version changes
    - PDF pipeline version changes
    - Cache structure changes
    """

    pdf_fingerprint = (
        get_pdf_fingerprint(
            pdf_path
        )
    )

    identity_payload = {
        "cache_version": (
            EVIDENCE_CACHE_VERSION
        ),
        "ocr_pipeline_version": (
            OCR_PIPELINE_VERSION
        ),
        "pdf_pipeline_version": (
            PDF_PIPELINE_VERSION
        ),
        "pdf_sha256": pdf_fingerprint,
        "page_number": page_number,
    }

    serialized_identity = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    cache_key = hashlib.sha256(
        serialized_identity.encode(
            "utf-8"
        )
    ).hexdigest()

    return cache_key, pdf_fingerprint


def load_cached_page_evidence(
    pdf_path: str | Path,
    page_number: int,
) -> dict[str, Any] | None:
    """
    Load cached PDF-page and OCR evidence.

    Invalid, incomplete or outdated cache records are ignored.
    """

    cache_key, pdf_fingerprint = (
        build_page_cache_identity(
            pdf_path=pdf_path,
            page_number=page_number,
        )
    )

    record_path = (
        RECORDS_DIRECTORY
        / f"{cache_key}.json"
    )

    if not record_path.exists():
        return None

    try:
        record = json.loads(
            record_path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None

    if (
        record.get("cache_version")
        != EVIDENCE_CACHE_VERSION
    ):
        return None

    if (
        record.get("ocr_pipeline_version")
        != OCR_PIPELINE_VERSION
    ):
        return None

    if (
        record.get("pdf_pipeline_version")
        != PDF_PIPELINE_VERSION
    ):
        return None

    if (
        record.get("pdf_sha256")
        != pdf_fingerprint
    ):
        return None

    if (
        record.get("page_number")
        != page_number
    ):
        return None

    status = record.get("status")

    valid_statuses = {
        "READY",
        "PAGE_MISSING",
        "TEXT_NOT_FOUND",
    }

    if status not in valid_statuses:
        return None

    image_path: str | None = None

    cached_image_name = record.get(
        "cached_image_name"
    )

    if cached_image_name:
        cached_image_path = (
            IMAGES_DIRECTORY
            / cached_image_name
        )

        if not cached_image_path.exists():
            return None

        image_path = str(
            cached_image_path
        )

    if (
        status in {
            "READY",
            "TEXT_NOT_FOUND",
        }
        and image_path is None
    ):
        return None

    return {
        "status": status,
        "pdf_exists": True,
        "page_exists": bool(
            record.get("page_exists")
        ),
        "image_path": image_path,
        "direct_pdf_text": str(
            record.get(
                "direct_pdf_text",
                "",
            )
        ),
        "ocr_text": str(
            record.get(
                "ocr_text",
                "",
            )
        ),
        "combined_evidence_text": str(
            record.get(
                "combined_evidence_text",
                "",
            )
        ),
        "message": str(
            record.get(
                "message",
                "Cached page evidence was loaded.",
            )
        ),
    }


def save_cached_page_evidence(
    pdf_path: str | Path,
    page_number: int,
    evidence: ClaimEvidence,
) -> None:
    """
    Save one PDF-page evidence result atomically.

    PDF_MISSING is intentionally not cached because the missing
    file may be uploaded later.
    """

    if evidence.status == "PDF_MISSING":
        return

    cache_key, pdf_fingerprint = (
        build_page_cache_identity(
            pdf_path=pdf_path,
            page_number=page_number,
        )
    )

    RECORDS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGES_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    cached_image_name: str | None = None

    if evidence.image_path:
        source_image_path = Path(
            evidence.image_path
        )

        if source_image_path.exists():
            image_suffix = (
                source_image_path.suffix.lower()
                or ".png"
            )

            cached_image_name = (
                f"{cache_key}{image_suffix}"
            )

            final_image_path = (
                IMAGES_DIRECTORY
                / cached_image_name
            )

            temporary_image_path = (
                IMAGES_DIRECTORY
                / f"{cached_image_name}.tmp"
            )

            shutil.copyfile(
                source_image_path,
                temporary_image_path,
            )

            os.replace(
                temporary_image_path,
                final_image_path,
            )

    record = {
        "cache_version": (
            EVIDENCE_CACHE_VERSION
        ),
        "ocr_pipeline_version": (
            OCR_PIPELINE_VERSION
        ),
        "pdf_pipeline_version": (
            PDF_PIPELINE_VERSION
        ),
        "pdf_sha256": pdf_fingerprint,
        "page_number": page_number,
        "status": evidence.status,
        "page_exists": evidence.page_exists,
        "cached_image_name": (
            cached_image_name
        ),
        "direct_pdf_text": (
            evidence.direct_pdf_text
        ),
        "ocr_text": evidence.ocr_text,
        "combined_evidence_text": (
            evidence.combined_evidence_text
        ),
        "message": evidence.message,
    }

    final_record_path = (
        RECORDS_DIRECTORY
        / f"{cache_key}.json"
    )

    temporary_record_path = (
        RECORDS_DIRECTORY
        / f"{cache_key}.json.tmp"
    )

    temporary_record_path.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    os.replace(
        temporary_record_path,
        final_record_path,
    )