from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

CACHE_ROOT = (
    PROJECT_ROOT
    / "cache"
    / "candidate_ocr"
)

RECORDS_DIRECTORY = (
    CACHE_ROOT
    / "records"
)

IMAGES_DIRECTORY = (
    CACHE_ROOT
    / "images"
)

CACHE_VERSION = "candidate-ocr-v1"

OCR_PIPELINE_VERSION = (
    "easyocr-adaptive-rotation-v1"
)


def build_cache_key(
    image_fingerprint: str,
) -> str:
    """
    Build a stable cache key from candidate image content.
    """

    payload = {
        "cache_version": CACHE_VERSION,
        "ocr_pipeline_version": (
            OCR_PIPELINE_VERSION
        ),
        "image_fingerprint": (
            image_fingerprint
        ),
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def load_cached_candidate_ocr(
    image_fingerprint: str,
) -> dict[str, Any] | None:
    """
    Load previously generated candidate OCR evidence.
    """

    cache_key = build_cache_key(
        image_fingerprint
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
        != CACHE_VERSION
    ):
        return None

    if (
        record.get("ocr_pipeline_version")
        != OCR_PIPELINE_VERSION
    ):
        return None

    if (
        record.get("image_fingerprint")
        != image_fingerprint
    ):
        return None

    selected_image_name = record.get(
        "selected_image_name"
    )

    if not selected_image_name:
        return None

    selected_image_path = (
        IMAGES_DIRECTORY
        / selected_image_name
    )

    if not selected_image_path.exists():
        return None

    return {
        "selected_rotation_degrees": int(
            record.get(
                "selected_rotation_degrees",
                0,
            )
        ),
        "tested_rotations": [
            int(rotation)
            for rotation
            in record.get(
                "tested_rotations",
                [0],
            )
        ],
        "selected_image_path": str(
            selected_image_path
        ),
        "ocr_text": str(
            record.get(
                "ocr_text",
                "",
            )
        ),
        "ocr_score": float(
            record.get(
                "ocr_score",
                0.0,
            )
        ),
    }


def save_cached_candidate_ocr(
    *,
    image_fingerprint: str,
    selected_rotation_degrees: int,
    tested_rotations: list[int],
    selected_image_path: str | Path,
    ocr_text: str,
    ocr_score: float,
) -> None:
    """
    Save candidate OCR evidence and the selected
    orientation image atomically.
    """

    source_image_path = Path(
        selected_image_path
    )

    if not source_image_path.exists():
        return

    cache_key = build_cache_key(
        image_fingerprint
    )

    RECORDS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGES_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    image_suffix = (
        source_image_path.suffix.lower()
        or ".png"
    )

    selected_image_name = (
        f"{cache_key}{image_suffix}"
    )

    final_image_path = (
        IMAGES_DIRECTORY
        / selected_image_name
    )

    temporary_image_path = (
        IMAGES_DIRECTORY
        / f"{selected_image_name}.tmp"
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
        "cache_version": CACHE_VERSION,
        "ocr_pipeline_version": (
            OCR_PIPELINE_VERSION
        ),
        "image_fingerprint": (
            image_fingerprint
        ),
        "selected_rotation_degrees": (
            selected_rotation_degrees
        ),
        "tested_rotations": (
            tested_rotations
        ),
        "selected_image_name": (
            selected_image_name
        ),
        "ocr_text": ocr_text,
        "ocr_score": ocr_score,
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