from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cv2
import fitz

from models.receipt_candidate import (
    ReceiptCandidate,
)
from models.receipt_candidate_evidence import (
    CandidateReceiptEvidence,
    PageReceiptCandidateEvidence,
)
from tools.candidate_ocr_cache_tool import (
    load_cached_candidate_ocr,
    save_cached_candidate_ocr,
)
from tools.receipt_candidate_detector import (
    detect_receipt_candidates,
    read_image,
    write_image,
)


ORIENTATION_ACCEPTANCE_SCORE = 62.0

RotationResult = dict[str, Any]


def normalize_text(
    text: str,
) -> str:
    """
    Remove blank lines and surrounding whitespace.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


def combine_candidate_text(
    direct_pdf_text: str,
    ocr_text: str,
) -> str:
    """
    Combine evidence for one candidate only.

    Evidence belonging to different candidates is
    never concatenated.
    """

    direct_text = normalize_text(
        direct_pdf_text
    )

    local_ocr_text = normalize_text(
        ocr_text
    )

    if (
        direct_text
        and direct_text.casefold()
        == local_ocr_text.casefold()
    ):
        return direct_text

    sections: list[str] = []

    if direct_text:
        sections.append(
            "DIRECT PDF TEXT:\n"
            + direct_text
        )

    if local_ocr_text:
        sections.append(
            "LOCAL OCR TEXT:\n"
            + local_ocr_text
        )

    return "\n\n".join(
        sections
    )


def calculate_receipt_text_score(
    text: str,
) -> float:
    """
    Calculate how strongly OCR text resembles
    payment or receipt evidence.

    This score is used only for selecting orientation.
    It does not approve reimbursement claims.
    """

    normalized = normalize_text(
        text
    )

    if not normalized:
        return 0.0

    lowered = normalized.casefold()

    score = 0.0

    score += min(
        24.0,
        len(normalized) / 12.0,
    )

    digit_count = sum(
        character.isdigit()
        for character in normalized
    )

    score += min(
        14.0,
        digit_count * 0.45,
    )

    receipt_keywords = [
        "amount",
        "total",
        "paid",
        "payment",
        "successful",
        "success",
        "transaction",
        "txn",
        "utr",
        "invoice",
        "receipt",
        "merchant",
        "date",
        "gst",
        "upi",
        "card",
        "cash",
        "bank",
    ]

    keyword_hits = sum(
        keyword in lowered
        for keyword in receipt_keywords
    )

    score += min(
        32.0,
        keyword_hits * 4.0,
    )

    amount_patterns = [
        r"₹\s*\d",
        r"\brs\.?\s*\d",
        r"\binr\s*\d",
        r"\d+[,.]\d{2}\b",
    ]

    if any(
        re.search(
            pattern,
            lowered,
            re.IGNORECASE,
        )
        for pattern in amount_patterns
    ):
        score += 12.0

    date_patterns = [
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        r"\b\d{1,2}\s+[a-z]{3,9}\s+\d{2,4}\b",
    ]

    if any(
        re.search(
            pattern,
            lowered,
            re.IGNORECASE,
        )
        for pattern in date_patterns
    ):
        score += 10.0

    identifier_patterns = [
        r"\btxn[-:\s]?[a-z0-9]",
        r"\butr[-:\s]?[a-z0-9]",
        r"\binvoice[-:\s]?[a-z0-9]",
        r"\btransaction\s+id\b",
    ]

    if any(
        re.search(
            pattern,
            lowered,
            re.IGNORECASE,
        )
        for pattern in identifier_patterns
    ):
        score += 8.0

    return round(
        min(
            100.0,
            score,
        ),
        3,
    )


def rotate_image(
    image,
    rotation_degrees: int,
):
    """
    Rotate a candidate image clockwise.
    """

    if rotation_degrees == 0:
        return image.copy()

    if rotation_degrees == 90:
        return cv2.rotate(
            image,
            cv2.ROTATE_90_CLOCKWISE,
        )

    if rotation_degrees == 180:
        return cv2.rotate(
            image,
            cv2.ROTATE_180,
        )

    if rotation_degrees == 270:
        return cv2.rotate(
            image,
            cv2.ROTATE_90_COUNTERCLOCKWISE,
        )

    raise ValueError(
        "Unsupported rotation value."
    )


def extract_clipped_pdf_text(
    pdf_path: str | Path,
    page_number: int,
    candidate: ReceiptCandidate,
) -> str:
    """
    Extract selectable PDF text only from the
    candidate's bounding region.
    """

    with fitz.open(
        str(pdf_path)
    ) as document:
        if (
            page_number < 1
            or page_number > document.page_count
        ):
            return ""

        page = document.load_page(
            page_number - 1
        )

        (
            x_min_ratio,
            y_min_ratio,
            x_max_ratio,
            y_max_ratio,
        ) = candidate.normalized_bounding_box

        page_rectangle = page.rect

        clip_rectangle = fitz.Rect(
            page_rectangle.x0
            + (
                page_rectangle.width
                * x_min_ratio
            ),
            page_rectangle.y0
            + (
                page_rectangle.height
                * y_min_ratio
            ),
            page_rectangle.x0
            + (
                page_rectangle.width
                * x_max_ratio
            ),
            page_rectangle.y0
            + (
                page_rectangle.height
                * y_max_ratio
            ),
        )

        return normalize_text(
            page.get_text(
                "text",
                clip=clip_rectangle,
            )
        )


def perform_candidate_ocr(
    candidate: ReceiptCandidate,
    output_directory: str | Path,
) -> dict[str, Any]:
    """
    OCR one candidate independently.

    The upright image is tested first. Other rotations
    are tested only when the initial result is weak.
    """

    cached_result = (
        load_cached_candidate_ocr(
            candidate.image_fingerprint
        )
    )

    if cached_result is not None:
        return {
            **cached_result,
            "from_cache": True,
        }

    from tools.ocr_tool import extract_text

    output_directory = Path(
        output_directory
    )

    rotation_directory = (
        output_directory
        / "rotations"
    )

    rotation_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_image = read_image(
        candidate.image_path
    )

    rotations_to_test = [0]

    rotation_results: list[
        RotationResult
    ] = []

    def evaluate_rotation(
        rotation_degrees: int,
    ) -> None:
        rotated_image = rotate_image(
            original_image,
            rotation_degrees,
        )

        rotated_image_path = (
            rotation_directory
            / (
                f"candidate_"
                f"{candidate.candidate_no:02d}"
                f"_rotation_"
                f"{rotation_degrees:03d}.png"
            )
        )

        write_image(
            rotated_image_path,
            rotated_image,
        )

        ocr_text = normalize_text(
            extract_text(
                str(
                    rotated_image_path
                )
            )
        )

        ocr_score = (
            calculate_receipt_text_score(
                ocr_text
            )
        )

        rotation_results.append(
            {
                "rotation_degrees": (
                    rotation_degrees
                ),
                "image_path": str(
                    rotated_image_path
                ),
                "ocr_text": ocr_text,
                "ocr_score": ocr_score,
            }
        )

    evaluate_rotation(0)

    first_result = (
        rotation_results[0]
    )

    if (
        first_result["ocr_score"]
        < ORIENTATION_ACCEPTANCE_SCORE
        or len(
            first_result["ocr_text"]
        )
        < 25
    ):
        rotations_to_test.extend(
            [
                90,
                180,
                270,
            ]
        )

        for rotation_degrees in [
            90,
            180,
            270,
        ]:
            evaluate_rotation(
                rotation_degrees
            )

    selected_result = max(
        rotation_results,
        key=lambda result: (
            result["ocr_score"],
            len(
                result["ocr_text"]
            ),
        ),
    )

    save_cached_candidate_ocr(
        image_fingerprint=(
            candidate.image_fingerprint
        ),
        selected_rotation_degrees=(
            selected_result[
                "rotation_degrees"
            ]
        ),
        tested_rotations=(
            rotations_to_test
        ),
        selected_image_path=(
            selected_result[
                "image_path"
            ]
        ),
        ocr_text=(
            selected_result[
                "ocr_text"
            ]
        ),
        ocr_score=(
            selected_result[
                "ocr_score"
            ]
        ),
    )

    return {
        "selected_rotation_degrees": (
            selected_result[
                "rotation_degrees"
            ]
        ),
        "tested_rotations": (
            rotations_to_test
        ),
        "selected_image_path": (
            selected_result[
                "image_path"
            ]
        ),
        "ocr_text": (
            selected_result[
                "ocr_text"
            ]
        ),
        "ocr_score": (
            selected_result[
                "ocr_score"
            ]
        ),
        "from_cache": False,
    }


def prepare_page_candidate_evidence(
    *,
    pdf_path: str | Path,
    page_number: int,
    rendered_image_path: str | Path,
    output_directory: str | Path,
) -> PageReceiptCandidateEvidence:
    """
    Detect and prepare separate evidence for every
    receipt candidate on one page.
    """

    pdf_path = Path(
        pdf_path
    )

    output_directory = Path(
        output_directory
    )

    detection = (
        detect_receipt_candidates(
            pdf_path=pdf_path,
            page_number=page_number,
            rendered_image_path=(
                rendered_image_path
            ),
            output_directory=(
                output_directory
                / "candidates"
            ),
        )
    )

    if detection.blank_page:
        return PageReceiptCandidateEvidence(
            detection=detection,
            candidate_count=0,
            text_candidate_count=0,
            candidates=[],
            message=(
                "The PDF page is blank. "
                "No receipt candidate was processed."
            ),
        )

    candidate_evidence: list[
        CandidateReceiptEvidence
    ] = []

    for candidate in detection.candidates:
        direct_pdf_text = (
            extract_clipped_pdf_text(
                pdf_path=pdf_path,
                page_number=page_number,
                candidate=candidate,
            )
        )

        ocr_result = (
            perform_candidate_ocr(
                candidate=candidate,
                output_directory=(
                    output_directory
                    / (
                        f"candidate_"
                        f"{candidate.candidate_no:02d}"
                    )
                ),
            )
        )

        ocr_text = normalize_text(
            ocr_result["ocr_text"]
        )

        combined_text = (
            combine_candidate_text(
                direct_pdf_text=(
                    direct_pdf_text
                ),
                ocr_text=ocr_text,
            )
        )

        text_found = bool(
            combined_text
        )

        candidate_evidence.append(
            CandidateReceiptEvidence(
                candidate=candidate,
                selected_rotation_degrees=(
                    ocr_result[
                        "selected_rotation_degrees"
                    ]
                ),
                tested_rotations=(
                    ocr_result[
                        "tested_rotations"
                    ]
                ),
                selected_image_path=(
                    ocr_result[
                        "selected_image_path"
                    ]
                ),
                direct_pdf_text=(
                    direct_pdf_text
                ),
                ocr_text=ocr_text,
                combined_evidence_text=(
                    combined_text
                ),
                ocr_score=(
                    ocr_result[
                        "ocr_score"
                    ]
                ),
                text_found=text_found,
                from_cache=(
                    ocr_result[
                        "from_cache"
                    ]
                ),
                message=(
                    "Candidate evidence prepared "
                    "independently."
                    if text_found
                    else
                    "No readable evidence was found "
                    "inside this candidate."
                ),
            )
        )

    text_candidate_count = sum(
        candidate.text_found
        for candidate in candidate_evidence
    )

    return PageReceiptCandidateEvidence(
        detection=detection,
        candidate_count=len(
            candidate_evidence
        ),
        text_candidate_count=(
            text_candidate_count
        ),
        candidates=(
            candidate_evidence
        ),
        message=(
            f"Prepared separate evidence for "
            f"{len(candidate_evidence)} candidate(s). "
            f"{text_candidate_count} candidate(s) "
            "contained readable evidence."
        ),
    )