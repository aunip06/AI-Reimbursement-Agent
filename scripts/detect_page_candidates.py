"""
Detect independent receipt or screenshot candidates
on one PDF page without changing reimbursement decisions.
"""

import argparse
from pathlib import Path

from tools.pdf_tool import (
    render_pdf_page,
)
from tools.receipt_candidate_detector import (
    detect_receipt_candidates,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect receipt candidates on one PDF page."
        )
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the PDF file.",
    )

    parser.add_argument(
        "--page",
        required=True,
        type=int,
        help="One-based PDF page number.",
    )

    parser.add_argument(
        "--output-dir",
        default="output/candidate_detection",
        help="Directory for candidate crops.",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    pdf_path = Path(
        arguments.pdf
    )

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}"
        )

    rendered_page = render_pdf_page(
        pdf_path=pdf_path,
        page_number=arguments.page,
    )

    page_output_directory = (
        Path(
            arguments.output_dir
        )
        / pdf_path.stem
        / f"page_{arguments.page:04d}"
    )

    detection = detect_receipt_candidates(
        pdf_path=pdf_path,
        page_number=arguments.page,
        rendered_image_path=(
            rendered_page.image_path
        ),
        output_directory=(
            page_output_directory
        ),
    )

    print(
        "\n========== CANDIDATE DETECTION ==========\n"
    )

    print(
        detection.model_dump_json(
            indent=2
        )
    )

    print(
        "\n========== OUTPUT ==========\n"
    )

    print(
        "Candidate count: "
        f"{detection.candidate_count}"
    )

    print(
        "Blank page: "
        f"{detection.blank_page}"
    )

    print(
        "Annotated image: "
        f"{detection.annotated_image_path}"
    )

    for candidate in detection.candidates:
        print(
            f"Candidate {candidate.candidate_no}: "
            f"{candidate.image_path}"
        )


if __name__ == "__main__":
    main()