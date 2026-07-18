from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np

from models.receipt_candidate import (
    PageCandidateDetection,
    PixelBoundingBox,
    ReceiptCandidate,
)


DETECTOR_VERSION = (
    "hybrid-receipt-candidate-v1"
)

MIN_CANDIDATE_AREA_RATIO = 0.025
MAX_CANDIDATE_AREA_RATIO = 0.985

MIN_WIDTH_RATIO = 0.10
MIN_HEIGHT_RATIO = 0.08

BLANK_NON_WHITE_RATIO = 0.0025
BLANK_EDGE_DENSITY = 0.0008
BLANK_STANDARD_DEVIATION = 3.0

Box = tuple[int, int, int, int]


def read_image(
    image_path: str | Path,
) -> np.ndarray:
    """
    Read an image safely, including Windows paths
    containing non-ASCII characters.
    """

    image_bytes = np.fromfile(
        str(image_path),
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        image_bytes,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            f"Unable to read image: {image_path}"
        )

    return image


def write_image(
    image_path: str | Path,
    image: np.ndarray,
) -> None:
    """
    Write an image safely on Windows.
    """

    output_path = Path(image_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    extension = (
        output_path.suffix
        if output_path.suffix
        else ".png"
    )

    success, encoded_image = cv2.imencode(
        extension,
        image,
    )

    if not success:
        raise ValueError(
            f"Unable to encode image: {output_path}"
        )

    encoded_image.tofile(
        str(output_path)
    )


def box_area(
    box: Box,
) -> int:
    """
    Return the area of a pixel bounding box.
    """

    x_min, y_min, x_max, y_max = box

    return max(
        0,
        x_max - x_min,
    ) * max(
        0,
        y_max - y_min,
    )


def clip_box(
    box: Box,
    image_width: int,
    image_height: int,
) -> Box:
    """
    Keep a bounding box within image boundaries.
    """

    x_min, y_min, x_max, y_max = box

    return (
        max(
            0,
            min(
                x_min,
                image_width - 1,
            ),
        ),
        max(
            0,
            min(
                y_min,
                image_height - 1,
            ),
        ),
        max(
            1,
            min(
                x_max,
                image_width,
            ),
        ),
        max(
            1,
            min(
                y_max,
                image_height,
            ),
        ),
    )


def expand_box(
    box: Box,
    image_width: int,
    image_height: int,
    padding_ratio: float = 0.012,
) -> Box:
    """
    Add padding around a candidate so shadows,
    rounded corners and edge text are retained.
    """

    x_min, y_min, x_max, y_max = box

    padding_x = max(
        4,
        int(
            image_width
            * padding_ratio
        ),
    )

    padding_y = max(
        4,
        int(
            image_height
            * padding_ratio
        ),
    )

    return clip_box(
        (
            x_min - padding_x,
            y_min - padding_y,
            x_max + padding_x,
            y_max + padding_y,
        ),
        image_width=image_width,
        image_height=image_height,
    )


def intersection_area(
    first_box: Box,
    second_box: Box,
) -> int:
    """
    Return the intersection area between two boxes.
    """

    x_min = max(
        first_box[0],
        second_box[0],
    )

    y_min = max(
        first_box[1],
        second_box[1],
    )

    x_max = min(
        first_box[2],
        second_box[2],
    )

    y_max = min(
        first_box[3],
        second_box[3],
    )

    if (
        x_max <= x_min
        or y_max <= y_min
    ):
        return 0

    return (
        x_max - x_min
    ) * (
        y_max - y_min
    )


def intersection_over_union(
    first_box: Box,
    second_box: Box,
) -> float:
    """
    Calculate intersection over union.
    """

    intersection = intersection_area(
        first_box,
        second_box,
    )

    union = (
        box_area(first_box)
        + box_area(second_box)
        - intersection
    )

    if union <= 0:
        return 0.0

    return intersection / union


def containment_ratio(
    inner_box: Box,
    outer_box: Box,
) -> float:
    """
    Return how much of inner_box lies inside outer_box.
    """

    inner_area = box_area(
        inner_box
    )

    if inner_area <= 0:
        return 0.0

    return (
        intersection_area(
            inner_box,
            outer_box,
        )
        / inner_area
    )


def calculate_page_statistics(
    image: np.ndarray,
) -> tuple[float, float, float]:
    """
    Calculate non-white ratio, edge density and
    grayscale standard deviation.
    """

    gray_image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    non_white_ratio = float(
        np.mean(
            gray_image < 245
        )
    )

    edges = cv2.Canny(
        gray_image,
        45,
        140,
    )

    edge_density = float(
        np.mean(
            edges > 0
        )
    )

    standard_deviation = float(
        np.std(
            gray_image
        )
    )

    return (
        non_white_ratio,
        edge_density,
        standard_deviation,
    )


def is_blank_page(
    non_white_ratio: float,
    edge_density: float,
    standard_deviation: float,
) -> bool:
    """
    Determine whether a rendered page is visually blank.
    """

    return (
        non_white_ratio
        <= BLANK_NON_WHITE_RATIO
        and edge_density
        <= BLANK_EDGE_DENSITY
        and standard_deviation
        <= BLANK_STANDARD_DEVIATION
    )


def proposal_is_large_enough(
    box: Box,
    image_width: int,
    image_height: int,
) -> bool:
    """
    Reject tiny icons, logos and text fragments.
    """

    x_min, y_min, x_max, y_max = box

    width = x_max - x_min
    height = y_max - y_min

    page_area = (
        image_width
        * image_height
    )

    area_ratio = (
        box_area(box)
        / page_area
    )

    width_ratio = (
        width
        / image_width
    )

    height_ratio = (
        height
        / image_height
    )

    return (
        MIN_CANDIDATE_AREA_RATIO
        <= area_ratio
        <= MAX_CANDIDATE_AREA_RATIO
        and width_ratio
        >= MIN_WIDTH_RATIO
        and height_ratio
        >= MIN_HEIGHT_RATIO
    )


def detect_native_pdf_images(
    pdf_path: str | Path,
    page_number: int,
    image_width: int,
    image_height: int,
) -> list[dict[str, Any]]:
    """
    Detect independent images embedded in the PDF page.

    PDF coordinates are converted into rendered-image pixels.
    """

    proposals: list[
        dict[str, Any]
    ] = []

    with fitz.open(
        str(pdf_path)
    ) as document:
        if (
            page_number < 1
            or page_number
            > document.page_count
        ):
            return []

        page = document.load_page(
            page_number - 1
        )

        page_width = float(
            page.rect.width
        )

        page_height = float(
            page.rect.height
        )

        if (
            page_width <= 0
            or page_height <= 0
        ):
            return []

        scale_x = (
            image_width
            / page_width
        )

        scale_y = (
            image_height
            / page_height
        )

        page_dictionary = (
            page.get_text(
                "dict"
            )
        )

        for block in page_dictionary.get(
            "blocks",
            [],
        ):
            if block.get("type") != 1:
                continue

            pdf_box = block.get(
                "bbox"
            )

            if (
                not pdf_box
                or len(pdf_box) != 4
            ):
                continue

            x_min = int(
                round(
                    pdf_box[0]
                    * scale_x
                )
            )

            y_min = int(
                round(
                    pdf_box[1]
                    * scale_y
                )
            )

            x_max = int(
                round(
                    pdf_box[2]
                    * scale_x
                )
            )

            y_max = int(
                round(
                    pdf_box[3]
                    * scale_y
                )
            )

            box = expand_box(
                (
                    x_min,
                    y_min,
                    x_max,
                    y_max,
                ),
                image_width=(
                    image_width
                ),
                image_height=(
                    image_height
                ),
            )

            if not proposal_is_large_enough(
                box=box,
                image_width=(
                    image_width
                ),
                image_height=(
                    image_height
                ),
            ):
                continue

            proposals.append(
                {
                    "box": box,
                    "source": (
                        "native_pdf_image"
                    ),
                    "confidence": 0.98,
                    "notes": [
                        (
                            "Candidate detected from an "
                            "embedded PDF image block."
                        )
                    ],
                }
            )

    return proposals


def add_contour_proposals(
    binary_image: np.ndarray,
    gray_image: np.ndarray,
    image_width: int,
    image_height: int,
    proposals: list[dict[str, Any]],
    detection_note: str,
) -> None:
    """
    Convert external contours into visual-region proposals.
    """

    contours, _ = cv2.findContours(
        binary_image,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    page_area = (
        image_width
        * image_height
    )

    for contour in contours:
        x, y, width, height = (
            cv2.boundingRect(
                contour
            )
        )

        raw_box = (
            x,
            y,
            x + width,
            y + height,
        )

        box = expand_box(
            raw_box,
            image_width=image_width,
            image_height=image_height,
        )

        if not proposal_is_large_enough(
            box=box,
            image_width=image_width,
            image_height=image_height,
        ):
            continue

        x_min, y_min, x_max, y_max = (
            box
        )

        region = gray_image[
            y_min:y_max,
            x_min:x_max,
        ]

        if region.size == 0:
            continue

        content_density = float(
            np.mean(
                region < 245
            )
        )

        if content_density < 0.012:
            continue

        contour_area = float(
            cv2.contourArea(
                contour
            )
        )

        bounding_area = float(
            max(
                1,
                width * height,
            )
        )

        rectangularity = min(
            1.0,
            contour_area
            / bounding_area,
        )

        area_ratio = (
            box_area(box)
            / page_area
        )

        confidence = min(
            0.95,
            (
                0.52
                + min(
                    0.18,
                    rectangularity
                    * 0.18,
                )
                + min(
                    0.15,
                    content_density
                    * 1.5,
                )
                + min(
                    0.10,
                    area_ratio,
                )
            ),
        )

        proposals.append(
            {
                "box": box,
                "source": (
                    "visual_region"
                ),
                "confidence": round(
                    confidence,
                    3,
                ),
                "notes": [
                    detection_note
                ],
            }
        )


def detect_visual_regions(
    image: np.ndarray,
) -> list[dict[str, Any]]:
    """
    Generate candidate proposals from a flattened page.

    Multiple detection maps are used so the detector can find:

    - bordered screenshots
    - borderless screenshots
    - photographs
    - large text-and-image clusters
    - screenshots in random page positions
    """

    image_height, image_width = (
        image.shape[:2]
    )

    gray_image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    blurred_image = cv2.GaussianBlur(
        gray_image,
        (5, 5),
        0,
    )

    edges = cv2.Canny(
        blurred_image,
        40,
        135,
    )

    _, dark_content = cv2.threshold(
        blurred_image,
        245,
        255,
        cv2.THRESH_BINARY_INV,
    )

    combined_map = cv2.bitwise_or(
        edges,
        dark_content,
    )

    minimum_dimension = min(
        image_width,
        image_height,
    )

    small_kernel_size = max(
        5,
        int(
            minimum_dimension
            * 0.006
        ),
    )

    small_kernel = (
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (
                small_kernel_size,
                small_kernel_size,
            ),
        )
    )

    closed_map = cv2.morphologyEx(
        combined_map,
        cv2.MORPH_CLOSE,
        small_kernel,
        iterations=2,
    )

    horizontal_kernel = max(
        15,
        int(
            image_width
            * 0.012
        ),
    )

    vertical_kernel = max(
        9,
        int(
            image_height
            * 0.007
        ),
    )

    grouping_kernel = (
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (
                horizontal_kernel,
                vertical_kernel,
            ),
        )
    )

    grouped_map = cv2.dilate(
        combined_map,
        grouping_kernel,
        iterations=2,
    )

    proposals: list[
        dict[str, Any]
    ] = []

    add_contour_proposals(
        binary_image=closed_map,
        gray_image=gray_image,
        image_width=image_width,
        image_height=image_height,
        proposals=proposals,
        detection_note=(
            "Candidate detected from closed "
            "visual edges and content."
        ),
    )

    add_contour_proposals(
        binary_image=grouped_map,
        gray_image=gray_image,
        image_width=image_width,
        image_height=image_height,
        proposals=proposals,
        detection_note=(
            "Candidate detected from grouped "
            "page-content regions."
        ),
    )

    return proposals


def remove_duplicate_proposals(
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove overlapping and nested detections.

    Native PDF image detections receive first priority,
    followed by the largest coherent visual regions.
    """

    source_priority = {
        "native_pdf_image": 3,
        "visual_region": 2,
        "full_page_fallback": 1,
    }

    ordered = sorted(
        proposals,
        key=lambda proposal: (
            source_priority.get(
                proposal["source"],
                0,
            ),
            box_area(
                proposal["box"]
            ),
            proposal["confidence"],
        ),
        reverse=True,
    )

    selected: list[
        dict[str, Any]
    ] = []

    for proposal in ordered:
        proposal_box = proposal[
            "box"
        ]

        should_skip = False

        for existing in selected:
            existing_box = existing[
                "box"
            ]

            overlap = (
                intersection_over_union(
                    proposal_box,
                    existing_box,
                )
            )

            proposal_inside_existing = (
                containment_ratio(
                    proposal_box,
                    existing_box,
                )
            )

            existing_inside_proposal = (
                containment_ratio(
                    existing_box,
                    proposal_box,
                )
            )

            if overlap >= 0.58:
                should_skip = True
                break

            if (
                proposal_inside_existing
                >= 0.88
            ):
                should_skip = True
                break

            if (
                existing[
                    "source"
                ]
                == "native_pdf_image"
                and proposal[
                    "source"
                ]
                == "visual_region"
                and existing_inside_proposal
                >= 0.90
                and box_area(
                    proposal_box
                )
                <= (
                    box_area(
                        existing_box
                    )
                    * 2.5
                )
            ):
                should_skip = True
                break

        if not should_skip:
            selected.append(
                proposal
            )

    # Remove one huge wrapper when it contains two or more
    # meaningful smaller candidates.
    final_proposals: list[
        dict[str, Any]
    ] = []

    for proposal in selected:
        proposal_box = proposal[
            "box"
        ]

        contained_candidates = [
            other
            for other in selected
            if other is not proposal
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.92
            and box_area(
                other["box"]
            )
            >= (
                box_area(
                    proposal_box
                )
                * 0.04
            )
        ]

        if (
            len(
                contained_candidates
            )
            >= 2
        ):
            continue

        final_proposals.append(
            proposal
        )

    return final_proposals


def crop_fingerprint(
    crop: np.ndarray,
) -> str:
    """
    Create an exact content fingerprint for one crop.
    """

    success, encoded_crop = (
        cv2.imencode(
            ".png",
            crop,
        )
    )

    if not success:
        raise ValueError(
            "Unable to encode candidate crop."
        )

    return hashlib.sha256(
        encoded_crop.tobytes()
    ).hexdigest()


def detect_receipt_candidates(
    pdf_path: str | Path,
    page_number: int,
    rendered_image_path: str | Path,
    output_directory: str | Path,
) -> PageCandidateDetection:
    """
    Detect independent screenshot or receipt candidates
    on one rendered PDF page.

    This function does not perform OCR and does not affect
    reimbursement decisions.
    """

    pdf_path = Path(
        pdf_path
    )

    rendered_image_path = Path(
        rendered_image_path
    )

    output_directory = Path(
        output_directory
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    image = read_image(
        rendered_image_path
    )

    image_height, image_width = (
        image.shape[:2]
    )

    (
        non_white_ratio,
        edge_density,
        standard_deviation,
    ) = calculate_page_statistics(
        image
    )

    page_is_blank = is_blank_page(
        non_white_ratio=(
            non_white_ratio
        ),
        edge_density=edge_density,
        standard_deviation=(
            standard_deviation
        ),
    )

    if page_is_blank:
        return PageCandidateDetection(
            pdf_file_name=(
                pdf_path.name
            ),
            page_number=page_number,
            page_width=image_width,
            page_height=image_height,
            blank_page=True,
            non_white_ratio=round(
                non_white_ratio,
                6,
            ),
            edge_density=round(
                edge_density,
                6,
            ),
            candidate_count=0,
            candidates=[],
            annotated_image_path=None,
            detector_version=(
                DETECTOR_VERSION
            ),
            message=(
                "The page appears visually blank. "
                "No receipt candidate was created."
            ),
        )

    proposals: list[
        dict[str, Any]
    ] = []

    proposals.extend(
        detect_native_pdf_images(
            pdf_path=pdf_path,
            page_number=page_number,
            image_width=image_width,
            image_height=image_height,
        )
    )

    proposals.extend(
        detect_visual_regions(
            image=image
        )
    )

    proposals = (
        remove_duplicate_proposals(
            proposals
        )
    )

    if not proposals:
        proposals = [
            {
                "box": (
                    0,
                    0,
                    image_width,
                    image_height,
                ),
                "source": (
                    "full_page_fallback"
                ),
                "confidence": 0.45,
                "notes": [
                    (
                        "No independent region was detected. "
                        "The full nonblank page was retained "
                        "for later AI layout review."
                    )
                ],
            }
        ]

    proposals = sorted(
        proposals,
        key=lambda proposal: (
            proposal["box"][1],
            proposal["box"][0],
        ),
    )

    candidates: list[
        ReceiptCandidate
    ] = []

    annotated_image = (
        image.copy()
    )

    page_area = (
        image_width
        * image_height
    )

    for candidate_index, proposal in enumerate(
        proposals,
        start=1,
    ):
        x_min, y_min, x_max, y_max = (
            clip_box(
                proposal["box"],
                image_width=image_width,
                image_height=image_height,
            )
        )

        crop = image[
            y_min:y_max,
            x_min:x_max,
        ]

        if crop.size == 0:
            continue

        candidate_path = (
            output_directory
            / (
                f"page_{page_number:04d}"
                f"_candidate_{candidate_index:02d}"
                ".png"
            )
        )

        write_image(
            candidate_path,
            crop,
        )

        fingerprint = (
            crop_fingerprint(
                crop
            )
        )

        normalized_box = (
            round(
                x_min
                / image_width,
                6,
            ),
            round(
                y_min
                / image_height,
                6,
            ),
            round(
                x_max
                / image_width,
                6,
            ),
            round(
                y_max
                / image_height,
                6,
            ),
        )

        area_ratio = (
            box_area(
                (
                    x_min,
                    y_min,
                    x_max,
                    y_max,
                )
            )
            / page_area
        )

        candidates.append(
            ReceiptCandidate(
                candidate_no=(
                    candidate_index
                ),
                page_number=(
                    page_number
                ),
                source=(
                    proposal["source"]
                ),
                bounding_box=(
                    PixelBoundingBox(
                        x_min=x_min,
                        y_min=y_min,
                        x_max=x_max,
                        y_max=y_max,
                    )
                ),
                normalized_bounding_box=(
                    normalized_box
                ),
                image_path=str(
                    candidate_path
                ),
                area_ratio=round(
                    area_ratio,
                    6,
                ),
                detection_confidence=(
                    proposal[
                        "confidence"
                    ]
                ),
                image_fingerprint=(
                    fingerprint
                ),
                notes=proposal[
                    "notes"
                ],
            )
        )

        cv2.rectangle(
            annotated_image,
            (
                x_min,
                y_min,
            ),
            (
                x_max,
                y_max,
            ),
            (
                0,
                0,
                255,
            ),
            4,
        )

        cv2.putText(
            annotated_image,
            f"Candidate {candidate_index}",
            (
                x_min + 8,
                max(
                    30,
                    y_min + 30,
                ),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (
                0,
                0,
                255,
            ),
            2,
            cv2.LINE_AA,
        )

    annotated_image_path = (
        output_directory
        / (
            f"page_{page_number:04d}"
            "_candidate_map.png"
        )
    )

    write_image(
        annotated_image_path,
        annotated_image,
    )

    return PageCandidateDetection(
        pdf_file_name=(
            pdf_path.name
        ),
        page_number=page_number,
        page_width=image_width,
        page_height=image_height,
        blank_page=False,
        non_white_ratio=round(
            non_white_ratio,
            6,
        ),
        edge_density=round(
            edge_density,
            6,
        ),
        candidate_count=len(
            candidates
        ),
        candidates=candidates,
        annotated_image_path=str(
            annotated_image_path
        ),
        detector_version=(
            DETECTOR_VERSION
        ),
        message=(
            f"Detected {len(candidates)} "
            "independent receipt candidate(s). "
            "The result is currently running in shadow mode."
        ),
    )