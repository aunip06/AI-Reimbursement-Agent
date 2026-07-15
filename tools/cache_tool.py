import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config import MODEL


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIRECTORY = PROJECT_ROOT / "cache"

RECEIPT_CACHE_VERSION = "receipt-extraction-v2"
ANALYSIS_CACHE_VERSION = "reimbursement-analysis-v1"


def normalize_ocr_text(ocr_text: str) -> str:
    """
    Normalize OCR text before generating a cache key.

    Empty lines and surrounding spaces are removed, but the
    original line order is preserved.
    """

    normalized_lines = [
        line.strip()
        for line in ocr_text.splitlines()
        if line.strip()
    ]

    return "\n".join(normalized_lines)


def normalize_claim_data(
    claim: BaseModel | dict[str, Any],
) -> dict[str, Any]:
    """
    Convert a Pydantic claim or dictionary into JSON-safe data.
    """

    if isinstance(claim, BaseModel):
        return claim.model_dump(mode="json")

    if isinstance(claim, dict):
        return claim

    raise TypeError(
        "Claim must be a Pydantic model or dictionary."
    )


def create_hash(payload: dict[str, Any]) -> str:
    """
    Create a stable SHA-256 hash from JSON-compatible data.
    """

    serialized_payload = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized_payload.encode("utf-8")
    ).hexdigest()


def build_receipt_cache_key(
    ocr_text: str,
) -> str:
    """
    Build a cache key for receipt-only extraction.
    """

    payload = {
        "cache_version": RECEIPT_CACHE_VERSION,
        "model": MODEL,
        "ocr_text": normalize_ocr_text(ocr_text),
    }

    return create_hash(payload)


def build_analysis_cache_key(
    claim: BaseModel | dict[str, Any],
    ocr_text: str,
) -> str:
    """
    Build a cache key for combined extraction and verification.

    Both the Excel claim and OCR evidence are included.
    """

    payload = {
        "cache_version": ANALYSIS_CACHE_VERSION,
        "model": MODEL,
        "claim": normalize_claim_data(claim),
        "ocr_text": normalize_ocr_text(ocr_text),
    }

    return create_hash(payload)


def get_cache_path(
    cache_key: str,
) -> Path:
    """
    Return the local JSON cache path for a cache key.
    """

    CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    return CACHE_DIRECTORY / f"{cache_key}.json"


def read_cache_file(
    cache_path: Path,
) -> dict[str, Any] | None:
    """
    Read a cached result safely.

    Invalid or corrupted cache files are ignored.
    """

    if not cache_path.exists():
        return None

    try:
        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            cached_data = json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return None

    if not isinstance(cached_data, dict):
        return None

    # New cache envelope format.
    if (
        "result" in cached_data
        and isinstance(cached_data["result"], dict)
    ):
        return cached_data["result"]

    # Backward compatibility with old plain-result cache files.
    return cached_data


def write_cache_file(
    cache_path: Path,
    result: dict[str, Any],
    cache_type: str,
    cache_version: str,
) -> Path:
    """
    Save a successful structured result atomically.
    """

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_document = {
        "cache_type": cache_type,
        "cache_version": cache_version,
        "model": MODEL,
        "result": result,
    }

    temporary_path = cache_path.with_suffix(
        ".tmp"
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            cache_document,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary_path.replace(cache_path)

    return cache_path


def load_cached_result(
    ocr_text: str,
) -> dict[str, Any] | None:
    """
    Load an existing receipt-extraction result.

    This function is retained for compatibility with the
    current receipt-only app.
    """

    cache_key = build_receipt_cache_key(
        ocr_text
    )

    return read_cache_file(
        get_cache_path(cache_key)
    )


def save_cached_result(
    ocr_text: str,
    result: dict[str, Any],
) -> Path:
    """
    Save a receipt-only extraction result.

    This function is retained for compatibility with the
    current receipt-only app.
    """

    cache_key = build_receipt_cache_key(
        ocr_text
    )

    return write_cache_file(
        cache_path=get_cache_path(cache_key),
        result=result,
        cache_type="receipt_extraction",
        cache_version=RECEIPT_CACHE_VERSION,
    )


def load_cached_analysis_result(
    claim: BaseModel | dict[str, Any],
    ocr_text: str,
) -> dict[str, Any] | None:
    """
    Load a combined reimbursement-analysis result.
    """

    cache_key = build_analysis_cache_key(
        claim=claim,
        ocr_text=ocr_text,
    )

    return read_cache_file(
        get_cache_path(cache_key)
    )


def save_cached_analysis_result(
    claim: BaseModel | dict[str, Any],
    ocr_text: str,
    result: dict[str, Any],
) -> Path:
    """
    Save a successful combined reimbursement-analysis result.
    """

    cache_key = build_analysis_cache_key(
        claim=claim,
        ocr_text=ocr_text,
    )

    return write_cache_file(
        cache_path=get_cache_path(cache_key),
        result=result,
        cache_type="reimbursement_analysis",
        cache_version=ANALYSIS_CACHE_VERSION,
    )