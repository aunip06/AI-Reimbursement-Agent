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


DETECTOR_VERSION = "hybrid-layout-receipt-v2.1"

MIN_CANDIDATE_AREA_RATIO = 0.018
MAX_CANDIDATE_AREA_RATIO = 0.985
MIN_WIDTH_RATIO = 0.08
MIN_HEIGHT_RATIO = 0.06

BLANK_NON_WHITE_RATIO = 0.0025
BLANK_EDGE_DENSITY = 0.0008
BLANK_STANDARD_DEVIATION = 3.0

NATIVE_CONFIDENCE = 0.995
XY_CUT_CONFIDENCE = 0.90
CONTOUR_CONFIDENCE = 0.70

Box = tuple[int, int, int, int]
Gutter = tuple[int, int]


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


def box_width(
    box: Box,
) -> int:
    return max(
        0,
        box[2] - box[0],
    )


def box_height(
    box: Box,
) -> int:
    return max(
        0,
        box[3] - box[1],
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

    clipped_x_min = max(
        0,
        min(
            x_min,
            max(
                0,
                image_width - 1,
            ),
        ),
    )

    clipped_y_min = max(
        0,
        min(
            y_min,
            max(
                0,
                image_height - 1,
            ),
        ),
    )

    clipped_x_max = max(
        clipped_x_min + 1,
        min(
            x_max,
            image_width,
        ),
    )

    clipped_y_max = max(
        clipped_y_min + 1,
        min(
            y_max,
            image_height,
        ),
    )

    return (
        clipped_x_min,
        clipped_y_min,
        clipped_x_max,
        clipped_y_max,
    )


def expand_box(
    box: Box,
    image_width: int,
    image_height: int,
    padding_ratio: float = 0.008,
) -> Box:
    """
    Add conservative padding without joining nearby receipts.
    """

    x_min, y_min, x_max, y_max = box

    padding_x = max(
        3,
        int(
            image_width
            * padding_ratio
        ),
    )

    padding_y = max(
        3,
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


def overlap_ratio(
    first_box: Box,
    second_box: Box,
) -> float:
    """
    Return intersection relative to the smaller box.
    """

    smaller_area = min(
        box_area(first_box),
        box_area(second_box),
    )

    if smaller_area <= 0:
        return 0.0

    return (
        intersection_area(
            first_box,
            second_box,
        )
        / smaller_area
    )


def vertical_overlap_ratio(
    first_box: Box,
    second_box: Box,
) -> float:
    """
    Return overlap of vertical spans relative to the shorter span.
    """

    overlap = max(
        0,
        min(
            first_box[3],
            second_box[3],
        )
        - max(
            first_box[1],
            second_box[1],
        ),
    )

    shorter_height = min(
        box_height(first_box),
        box_height(second_box),
    )

    if shorter_height <= 0:
        return 0.0

    return overlap / shorter_height


def horizontal_overlap_ratio(
    first_box: Box,
    second_box: Box,
) -> float:
    """
    Return overlap of horizontal spans relative to the shorter span.
    """

    overlap = max(
        0,
        min(
            first_box[2],
            second_box[2],
        )
        - max(
            first_box[0],
            second_box[0],
        ),
    )

    shorter_width = min(
        box_width(first_box),
        box_width(second_box),
    )

    if shorter_width <= 0:
        return 0.0

    return overlap / shorter_width


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

    page_area = max(
        1,
        image_width
        * image_height,
    )

    area_ratio = (
        box_area(box)
        / page_area
    )

    width_ratio = (
        box_width(box)
        / max(
            1,
            image_width,
        )
    )

    height_ratio = (
        box_height(box)
        / max(
            1,
            image_height,
        )
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


def build_content_mask(
    image: np.ndarray,
) -> np.ndarray:
    """
    Build a conservative page-content mask.

    It retains screenshot boundaries and meaningful page content
    without the large directional dilation that previously merged
    neighbouring receipts.
    """

    gray_image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    blurred_image = cv2.GaussianBlur(
        gray_image,
        (3, 3),
        0,
    )

    _, dark_content = cv2.threshold(
        blurred_image,
        248,
        255,
        cv2.THRESH_BINARY_INV,
    )

    edges = cv2.Canny(
        blurred_image,
        35,
        125,
    )

    combined = cv2.bitwise_or(
        dark_content,
        edges,
    )

    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2, 2),
    )

    cleaned = cv2.morphologyEx(
        combined,
        cv2.MORPH_OPEN,
        open_kernel,
        iterations=1,
    )

    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (5, 5),
    )

    return cv2.morphologyEx(
        cleaned,
        cv2.MORPH_CLOSE,
        close_kernel,
        iterations=1,
    )


def contiguous_runs(
    values: np.ndarray,
) -> list[Gutter]:
    """
    Convert a Boolean one-dimensional array into runs.
    """

    runs: list[Gutter] = []
    run_start: int | None = None

    for index, is_active in enumerate(
        values.tolist()
    ):
        if is_active and run_start is None:
            run_start = index

        elif (
            not is_active
            and run_start is not None
        ):
            runs.append(
                (
                    run_start,
                    index,
                )
            )

            run_start = None

    if run_start is not None:
        runs.append(
            (
                run_start,
                len(values),
            )
        )

    return runs


def find_axis_gutters(
    mask: np.ndarray,
    axis: int,
    minimum_run: int,
    maximum_density: float,
) -> list[Gutter]:
    """
    Find long near-empty bands along one page axis.
    """

    density = np.mean(
        mask > 0,
        axis=axis,
    )

    low_density = (
        density
        <= maximum_density
    )

    return [
        run
        for run in contiguous_runs(
            low_density
        )
        if (
            run[1] - run[0]
            >= minimum_run
        )
    ]


def find_page_gutters(
    content_mask: np.ndarray,
) -> tuple[
    list[Gutter],
    list[Gutter],
]:
    """
    Find strong vertical and horizontal whitespace gutters.
    """

    image_height, image_width = (
        content_mask.shape[:2]
    )

    vertical_gutters = (
        find_axis_gutters(
            mask=content_mask,
            axis=0,
            minimum_run=max(
                10,
                int(
                    image_width
                    * 0.012
                ),
            ),
            maximum_density=0.006,
        )
    )

    horizontal_gutters = (
        find_axis_gutters(
            mask=content_mask,
            axis=1,
            minimum_run=max(
                10,
                int(
                    image_height
                    * 0.010
                ),
            ),
            maximum_density=0.006,
        )
    )

    return (
        vertical_gutters,
        horizontal_gutters,
    )


def content_bbox(
    content_mask: np.ndarray,
    region: Box,
    image_width: int,
    image_height: int,
) -> Box | None:
    """
    Tighten a region around actual visible content.
    """

    x_min, y_min, x_max, y_max = (
        clip_box(
            region,
            image_width,
            image_height,
        )
    )

    sub_mask = content_mask[
        y_min:y_max,
        x_min:x_max,
    ]

    points = cv2.findNonZero(
        sub_mask
    )

    if points is None:
        return None

    x, y, width, height = (
        cv2.boundingRect(
            points
        )
    )

    return expand_box(
        (
            x_min + x,
            y_min + y,
            x_min + x + width,
            y_min + y + height,
        ),
        image_width=image_width,
        image_height=image_height,
        padding_ratio=0.006,
    )


def region_content_ratio(
    content_mask: np.ndarray,
    region: Box,
) -> float:
    """
    Return visible-content density inside a region.
    """

    x_min, y_min, x_max, y_max = region

    sub_mask = content_mask[
        y_min:y_max,
        x_min:x_max,
    ]

    if sub_mask.size == 0:
        return 0.0

    return float(
        np.mean(
            sub_mask > 0
        )
    )


def find_best_split(
    content_mask: np.ndarray,
    region: Box,
) -> tuple[
    str,
    Gutter,
] | None:
    """
    Find the strongest valid whitespace split inside one region.

    The split must leave meaningful content on both sides.
    """

    x_min, y_min, x_max, y_max = region

    region_width = (
        x_max - x_min
    )

    region_height = (
        y_max - y_min
    )

    if (
        region_width < 120
        or region_height < 120
    ):
        return None

    sub_mask = content_mask[
        y_min:y_max,
        x_min:x_max,
    ]

    vertical_runs = (
        find_axis_gutters(
            mask=sub_mask,
            axis=0,
            minimum_run=max(
                10,
                int(
                    region_width
                    * 0.020
                ),
            ),
            maximum_density=0.004,
        )
    )

    horizontal_runs = (
        find_axis_gutters(
            mask=sub_mask,
            axis=1,
            minimum_run=max(
                10,
                int(
                    region_height
                    * 0.018
                ),
            ),
            maximum_density=0.004,
        )
    )

    candidates: list[
        tuple[
            float,
            str,
            Gutter,
        ]
    ] = []

    for start, end in vertical_runs:
        if (
            start
            < region_width * 0.12
            or end
            > region_width * 0.88
        ):
            continue

        left_region = (
            x_min,
            y_min,
            x_min + start,
            y_max,
        )

        right_region = (
            x_min + end,
            y_min,
            x_max,
            y_max,
        )

        left_ratio = (
            region_content_ratio(
                content_mask,
                left_region,
            )
        )

        right_ratio = (
            region_content_ratio(
                content_mask,
                right_region,
            )
        )

        if (
            left_ratio < 0.008
            or right_ratio < 0.008
        ):
            continue

        balance = min(
            box_area(left_region),
            box_area(right_region),
        ) / max(
            1,
            max(
                box_area(left_region),
                box_area(right_region),
            ),
        )

        score = (
            (end - start)
            / region_width
            + balance * 0.25
        )

        candidates.append(
            (
                score,
                "vertical",
                (
                    x_min + start,
                    x_min + end,
                ),
            )
        )

    for start, end in horizontal_runs:
        if (
            start
            < region_height * 0.12
            or end
            > region_height * 0.88
        ):
            continue

        top_region = (
            x_min,
            y_min,
            x_max,
            y_min + start,
        )

        bottom_region = (
            x_min,
            y_min + end,
            x_max,
            y_max,
        )

        top_ratio = (
            region_content_ratio(
                content_mask,
                top_region,
            )
        )

        bottom_ratio = (
            region_content_ratio(
                content_mask,
                bottom_region,
            )
        )

        if (
            top_ratio < 0.008
            or bottom_ratio < 0.008
        ):
            continue

        balance = min(
            box_area(top_region),
            box_area(bottom_region),
        ) / max(
            1,
            max(
                box_area(top_region),
                box_area(bottom_region),
            ),
        )

        score = (
            (end - start)
            / region_height
            + balance * 0.25
        )

        candidates.append(
            (
                score,
                "horizontal",
                (
                    y_min + start,
                    y_min + end,
                ),
            )
        )

    if not candidates:
        return None

    _, split_axis, split_band = max(
        candidates,
        key=lambda item: item[0],
    )

    return (
        split_axis,
        split_band,
    )


def recursive_xy_cut(
    content_mask: np.ndarray,
    region: Box,
    image_width: int,
    image_height: int,
    depth: int = 0,
    maximum_depth: int = 5,
) -> list[Box]:
    """
    Recursively split the page along strong whitespace gutters.
    """

    tightened = content_bbox(
        content_mask=content_mask,
        region=region,
        image_width=image_width,
        image_height=image_height,
    )

    if tightened is None:
        return []

    if depth >= maximum_depth:
        return [
            tightened
        ]

    split = find_best_split(
        content_mask=content_mask,
        region=tightened,
    )

    if split is None:
        return [
            tightened
        ]

    split_axis, (
        split_start,
        split_end,
    ) = split

    x_min, y_min, x_max, y_max = (
        tightened
    )

    if split_axis == "vertical":
        first_region = (
            x_min,
            y_min,
            split_start,
            y_max,
        )

        second_region = (
            split_end,
            y_min,
            x_max,
            y_max,
        )

    else:
        first_region = (
            x_min,
            y_min,
            x_max,
            split_start,
        )

        second_region = (
            x_min,
            split_end,
            x_max,
            y_max,
        )

    first_boxes = recursive_xy_cut(
        content_mask=content_mask,
        region=first_region,
        image_width=image_width,
        image_height=image_height,
        depth=depth + 1,
        maximum_depth=maximum_depth,
    )

    second_boxes = recursive_xy_cut(
        content_mask=content_mask,
        region=second_region,
        image_width=image_width,
        image_height=image_height,
        depth=depth + 1,
        maximum_depth=maximum_depth,
    )

    if (
        not first_boxes
        or not second_boxes
    ):
        return [
            tightened
        ]

    return (
        first_boxes
        + second_boxes
    )


def detect_xy_cut_regions(
    image: np.ndarray,
    content_mask: np.ndarray,
) -> list[dict[str, Any]]:
    """
    Detect page regions through global whitespace segmentation.
    """

    image_height, image_width = (
        image.shape[:2]
    )

    initial_region = (
        0,
        0,
        image_width,
        image_height,
    )

    boxes = recursive_xy_cut(
        content_mask=content_mask,
        region=initial_region,
        image_width=image_width,
        image_height=image_height,
    )

    proposals: list[
        dict[str, Any]
    ] = []

    for box in boxes:
        if not proposal_is_large_enough(
            box=box,
            image_width=image_width,
            image_height=image_height,
        ):
            continue

        density = region_content_ratio(
            content_mask,
            box,
        )

        if density < 0.010:
            continue

        confidence = min(
            0.94,
            XY_CUT_CONFIDENCE
            + min(
                0.04,
                density * 0.10,
            ),
        )

        proposals.append(
            {
                "box": box,
                "source": "visual_region",
                "confidence": round(
                    confidence,
                    3,
                ),
                "notes": [
                    (
                        "Candidate detected through recursive "
                        "whitespace and gutter segmentation."
                    )
                ],
                "method": "xy_cut",
            }
        )

    return proposals


def detect_contour_regions(
    image: np.ndarray,
    content_mask: np.ndarray,
) -> list[dict[str, Any]]:
    """
    Generate conservative contour proposals.

    No large directional dilation is used, preventing nearby
    receipts from being joined into a synthetic cross-page box.
    """

    image_height, image_width = (
        image.shape[:2]
    )

    contour_mask = cv2.morphologyEx(
        content_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (7, 7),
        ),
        iterations=1,
    )

    contours, _ = cv2.findContours(
        contour_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    proposals: list[
        dict[str, Any]
    ] = []

    page_area = max(
        1,
        image_width
        * image_height,
    )

    for contour in contours:
        x, y, width, height = (
            cv2.boundingRect(
                contour
            )
        )

        box = expand_box(
            (
                x,
                y,
                x + width,
                y + height,
            ),
            image_width=image_width,
            image_height=image_height,
            padding_ratio=0.006,
        )

        if not proposal_is_large_enough(
            box=box,
            image_width=image_width,
            image_height=image_height,
        ):
            continue

        density = region_content_ratio(
            content_mask,
            box,
        )

        if density < 0.014:
            continue

        contour_area = float(
            cv2.contourArea(
                contour
            )
        )

        rectangularity = min(
            1.0,
            contour_area
            / max(
                1.0,
                float(
                    width
                    * height
                ),
            ),
        )

        area_ratio = (
            box_area(box)
            / page_area
        )

        confidence = min(
            0.84,
            CONTOUR_CONFIDENCE
            + rectangularity * 0.08
            + min(
                0.04,
                density * 0.08,
            )
            + min(
                0.02,
                area_ratio * 0.02,
            ),
        )

        proposals.append(
            {
                "box": box,
                "source": "visual_region",
                "confidence": round(
                    confidence,
                    3,
                ),
                "notes": [
                    (
                        "Candidate detected from a conservative "
                        "connected visual region."
                    )
                ],
                "method": "contour",
            }
        )

    return proposals


def detect_native_pdf_images(
    pdf_path: str | Path,
    page_number: int,
    image_width: int,
    image_height: int,
) -> list[dict[str, Any]]:
    """
    Detect independent images embedded in the PDF page.

    Embedded images are the strongest source of screenshot
    boundaries and are treated as primary layout regions.
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

        page_dictionary = page.get_text(
            "dict"
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

            box = expand_box(
                (
                    int(
                        round(
                            pdf_box[0]
                            * scale_x
                        )
                    ),
                    int(
                        round(
                            pdf_box[1]
                            * scale_y
                        )
                    ),
                    int(
                        round(
                            pdf_box[2]
                            * scale_x
                        )
                    ),
                    int(
                        round(
                            pdf_box[3]
                            * scale_y
                        )
                    ),
                ),
                image_width=image_width,
                image_height=image_height,
                padding_ratio=0.004,
            )

            if not proposal_is_large_enough(
                box=box,
                image_width=image_width,
                image_height=image_height,
            ):
                continue

            proposals.append(
                {
                    "box": box,
                    "source": "native_pdf_image",
                    "confidence": NATIVE_CONFIDENCE,
                    "notes": [
                        (
                            "Candidate detected from an exact "
                            "embedded PDF image block."
                        )
                    ],
                    "method": "native",
                }
            )

    return proposals


def remove_near_duplicates(
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove near-identical boxes while keeping the strongest source.
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
            proposal["confidence"],
            box_area(
                proposal["box"]
            ),
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

        duplicate = any(
            (
                intersection_over_union(
                    proposal_box,
                    existing["box"],
                )
                >= 0.72
            )
            or (
                overlap_ratio(
                    proposal_box,
                    existing["box"],
                )
                >= 0.92
                and abs(
                    box_area(
                        proposal_box
                    )
                    - box_area(
                        existing["box"]
                    )
                )
                / max(
                    1,
                    max(
                        box_area(
                            proposal_box
                        ),
                        box_area(
                            existing["box"]
                        ),
                    ),
                )
                <= 0.35
            )
            for existing in selected
        )

        if not duplicate:
            selected.append(
                proposal
            )

    return selected


def proposal_crosses_native_layout(
    proposal: dict[str, Any],
    native_proposals: list[
        dict[str, Any]
    ],
) -> bool:
    """
    Reject a visual proposal that combines or duplicates
    established native screenshot regions.
    """

    proposal_box = proposal[
        "box"
    ]

    proposal_area = max(
        1,
        box_area(
            proposal_box
        ),
    )

    meaningful_native_overlaps: list[
        tuple[
            dict[str, Any],
            float,
            float,
        ]
    ] = []

    for native in native_proposals:
        native_box = native[
            "box"
        ]

        intersection = (
            intersection_area(
                proposal_box,
                native_box,
            )
        )

        if intersection <= 0:
            continue

        proposal_fraction = (
            intersection
            / proposal_area
        )

        native_fraction = (
            intersection
            / max(
                1,
                box_area(
                    native_box
                ),
            )
        )

        if (
            proposal_fraction >= 0.04
            or native_fraction >= 0.10
        ):
            meaningful_native_overlaps.append(
                (
                    native,
                    proposal_fraction,
                    native_fraction,
                )
            )

        if (
            containment_ratio(
                proposal_box,
                native_box,
            )
            >= 0.42
        ):
            return True

        if (
            containment_ratio(
                native_box,
                proposal_box,
            )
            >= 0.70
        ):
            return True

        if (
            intersection_over_union(
                proposal_box,
                native_box,
            )
            >= 0.22
        ):
            return True

    if len(
        meaningful_native_overlaps
    ) >= 2:
        return True

    total_native_coverage = sum(
        intersection_area(
            proposal_box,
            native["box"],
        )
        for native in native_proposals
    ) / proposal_area

    return total_native_coverage >= 0.18


def proposal_crosses_gutter_layout(
    proposal: dict[str, Any],
    all_proposals: list[
        dict[str, Any]
    ],
    vertical_gutters: list[Gutter],
    horizontal_gutters: list[Gutter],
) -> bool:
    """
    Reject a wrapper that crosses a strong gutter while
    meaningful child proposals exist on both sides.
    """

    proposal_box = proposal[
        "box"
    ]

    proposal_area = max(
        1,
        box_area(
            proposal_box
        ),
    )

    for gutter_start, gutter_end in (
        vertical_gutters
    ):
        if not (
            proposal_box[0]
            < gutter_start
            and proposal_box[2]
            > gutter_end
        ):
            continue

        left_children = [
            other
            for other in all_proposals
            if other is not proposal
            and other["box"][2]
            <= gutter_end
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.70
            and vertical_overlap_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.50
            and box_area(
                other["box"]
            )
            >= proposal_area * 0.06
        ]

        right_children = [
            other
            for other in all_proposals
            if other is not proposal
            and other["box"][0]
            >= gutter_start
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.70
            and vertical_overlap_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.50
            and box_area(
                other["box"]
            )
            >= proposal_area * 0.06
        ]

        if (
            left_children
            and right_children
        ):
            return True

    for gutter_start, gutter_end in (
        horizontal_gutters
    ):
        if not (
            proposal_box[1]
            < gutter_start
            and proposal_box[3]
            > gutter_end
        ):
            continue

        top_children = [
            other
            for other in all_proposals
            if other is not proposal
            and other["box"][3]
            <= gutter_end
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.70
            and horizontal_overlap_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.50
            and box_area(
                other["box"]
            )
            >= proposal_area * 0.06
        ]

        bottom_children = [
            other
            for other in all_proposals
            if other is not proposal
            and other["box"][1]
            >= gutter_start
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.70
            and horizontal_overlap_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.50
            and box_area(
                other["box"]
            )
            >= proposal_area * 0.06
        ]

        if (
            top_children
            and bottom_children
        ):
            return True

    return False


def proposal_is_multi_child_wrapper(
    proposal: dict[str, Any],
    all_proposals: list[
        dict[str, Any]
    ],
) -> bool:
    """
    Reject a large wrapper containing multiple stronger regions.
    """

    proposal_box = proposal[
        "box"
    ]

    proposal_area = max(
        1,
        box_area(
            proposal_box
        ),
    )

    children = [
        other
        for other in all_proposals
        if other is not proposal
        and other["confidence"]
        >= proposal["confidence"]
        and containment_ratio(
            other["box"],
            proposal_box,
        )
        >= 0.72
        and box_area(
            other["box"]
        )
        >= proposal_area * 0.05
    ]

    if len(children) < 2:
        return False

    covered_area = sum(
        min(
            box_area(
                child["box"]
            ),
            intersection_area(
                child["box"],
                proposal_box,
            ),
        )
        for child in children
    )

    return (
        covered_area
        / proposal_area
        >= 0.18
    )


def boxes_conflict(
    first_box: Box,
    second_box: Box,
) -> bool:
    """
    Determine whether two final candidates conflict.
    """

    if (
        intersection_over_union(
            first_box,
            second_box,
        )
        >= 0.18
    ):
        return True

    if (
        overlap_ratio(
            first_box,
            second_box,
        )
        >= 0.38
    ):
        return True

    if (
        containment_ratio(
            first_box,
            second_box,
        )
        >= 0.58
    ):
        return True

    if (
        containment_ratio(
            second_box,
            first_box,
        )
        >= 0.58
    ):
        return True

    return False


def select_global_layout(
    native_proposals: list[
        dict[str, Any]
    ],
    visual_proposals: list[
        dict[str, Any]
    ],
    vertical_gutters: list[Gutter],
    horizontal_gutters: list[Gutter],
) -> list[dict[str, Any]]:
    """
    Select one globally consistent set of receipt candidates.

    Native image blocks are authoritative. Visual proposals are
    admitted only when they represent uncovered page regions and
    do not mix, duplicate or cross the established layout.
    """

    native_proposals = (
        remove_near_duplicates(
            native_proposals
        )
    )

    visual_proposals = (
        remove_near_duplicates(
            visual_proposals
        )
    )

    all_proposals = (
        native_proposals
        + visual_proposals
    )

    filtered_visuals = [
        proposal
        for proposal in visual_proposals
        if not proposal_crosses_native_layout(
            proposal,
            native_proposals,
        )
        and not proposal_crosses_gutter_layout(
            proposal,
            all_proposals,
            vertical_gutters,
            horizontal_gutters,
        )
        and not proposal_is_multi_child_wrapper(
            proposal,
            all_proposals,
        )
    ]

    selected: list[
        dict[str, Any]
    ] = list(
        native_proposals
    )

    method_priority = {
        "xy_cut": 2,
        "contour": 1,
    }

    ordered_visuals = sorted(
        filtered_visuals,
        key=lambda proposal: (
            method_priority.get(
                proposal.get(
                    "method",
                    "",
                ),
                0,
            ),
            proposal["confidence"],
            box_area(
                proposal["box"]
            ),
        ),
        reverse=True,
    )

    for proposal in ordered_visuals:
        if any(
            boxes_conflict(
                proposal["box"],
                existing["box"],
            )
            for existing in selected
        ):
            continue

        selected.append(
            proposal
        )

    if not native_proposals:
        selected = [
            proposal
            for proposal in selected
            if not proposal_is_multi_child_wrapper(
                proposal,
                selected,
            )
        ]

    return remove_near_duplicates(
        selected
    )


def cleanup_old_page_outputs(
    output_directory: Path,
    page_number: int,
) -> None:
    """
    Remove stale candidate crops from an earlier detector run.
    """

    patterns = [
        (
            f"page_{page_number:04d}"
            "_candidate_*.png"
        ),
        (
            f"page_{page_number:04d}"
            "_candidate_map.png"
        ),
    ]

    for pattern in patterns:
        for path in output_directory.glob(
            pattern
        ):
            path.unlink(
                missing_ok=True
            )


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
    using a globally consistent page-layout model.

    Detection order:
    1. Exact embedded PDF images.
    2. Recursive whitespace and gutter segmentation.
    3. Conservative visual contours.
    4. Global conflict and wrapper rejection.
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

    cleanup_old_page_outputs(
        output_directory,
        page_number,
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

    content_mask = build_content_mask(
        image
    )

    (
        vertical_gutters,
        horizontal_gutters,
    ) = find_page_gutters(
        content_mask
    )

    native_proposals = (
        detect_native_pdf_images(
            pdf_path=pdf_path,
            page_number=page_number,
            image_width=image_width,
            image_height=image_height,
        )
    )

    visual_proposals = (
        detect_xy_cut_regions(
            image=image,
            content_mask=content_mask,
        )
        + detect_contour_regions(
            image=image,
            content_mask=content_mask,
        )
    )

    proposals = select_global_layout(
        native_proposals=(
            native_proposals
        ),
        visual_proposals=(
            visual_proposals
        ),
        vertical_gutters=(
            vertical_gutters
        ),
        horizontal_gutters=(
            horizontal_gutters
        ),
    )

    # Do not convert an uncertain multi-document page into one
    # full-page candidate. Returning zero candidates is safer than
    # mixing evidence from unrelated receipts. A later AI-layout
    # fallback can be added above this point without changing the
    # OCR or extraction contracts.
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

    page_area = max(
        1,
        image_width
        * image_height,
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

        notes = list(
            proposal.get(
                "notes",
                [],
            )
        )

        notes.append(
            (
                "Global layout method: "
                f"{proposal.get('method', 'unknown')}."
            )
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
                detection_confidence=float(
                    proposal[
                        "confidence"
                    ]
                ),
                image_fingerprint=(
                    fingerprint
                ),
                notes=notes,
            )
        )

        label = (
            f"Candidate {candidate_index}"
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
            label,
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
            (
                f"Detected {len(candidates)} independent "
                "receipt candidate(s) using global layout "
                "selection."
            )
            if candidates
            else (
                "No globally consistent receipt layout could "
                "be established. No mixed full-page candidate "
                "was created."
            )
        ),
    )
