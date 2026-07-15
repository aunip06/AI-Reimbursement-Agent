import hashlib
import json
from pathlib import Path
from typing import Any

from config import CACHE_FOLDER, MODEL


# Change this value whenever the extraction prompt or schema changes.
CACHE_VERSION = "receipt-extraction-v2"


def build_cache_key(ocr_text: str) -> str:
    """
    Create a unique cache key using:
    - cache version
    - OpenAI model
    - OCR text
    """
    normalized_text = ocr_text.strip()

    cache_content = (
        f"{CACHE_VERSION}\n"
        f"{MODEL}\n"
        f"{normalized_text}"
    )

    return hashlib.sha256(
        cache_content.encode("utf-8")
    ).hexdigest()


def get_cache_path(cache_key: str) -> Path:
    """
    Return the JSON cache file path.
    """
    cache_directory = Path(CACHE_FOLDER)
    cache_directory.mkdir(parents=True, exist_ok=True)

    return cache_directory / f"{cache_key}.json"


def load_cached_result(ocr_text: str) -> dict[str, Any] | None:
    """
    Load an existing cached extraction result.

    Returns None when no valid cache exists.
    """
    cache_key = build_cache_key(ocr_text)
    cache_path = get_cache_path(cache_key)

    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        return None


def save_cached_result(
    ocr_text: str,
    result: dict[str, Any],
) -> Path:
    """
    Save an extraction result as a JSON cache file.
    """
    cache_key = build_cache_key(ocr_text)
    cache_path = get_cache_path(cache_key)

    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return cache_path

