"""
Detect and OCR every receipt candidate on one PDF page
while preserving each candidate as separate evidence.
"""

import argparse
from pathlib import Path

from tools.pdf_tool import (
    render_pdf_page,
)
from workflow.receipt_candidate_evidence_workflow import (
    prepare_page_candidate_evidence,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect and OCR separate receipt candidates."
        )
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the PDF.",
    )

    parser.add_argument(
        "--page",
        required=True,
        type=int,
        help="One-based PDF page number.",
    )

    parser.add_argument(
        "--output-dir",
        default="output/candidate_evidence",
        help="Directory for crops and evidence.",
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

    evidence = (
        prepare_page_candidate_evidence(
            pdf_path=pdf_path,
            page_number=arguments.page,
            rendered_image_path=(
                rendered_page.image_path
            ),
            output_directory=(
                page_output_directory
            ),
        )
    )

    json_path = (
        page_output_directory
        / (
            f"page_{arguments.page:04d}"
            "_candidate_evidence.json"
        )
    )

    json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path.write_text(
        evidence.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        "\n========== PAGE CANDIDATE EVIDENCE ==========\n"
    )

    print(
        f"Blank page: "
        f"{evidence.detection.blank_page}"
    )

    print(
        f"Detected candidates: "
        f"{evidence.candidate_count}"
    )

    print(
        f"Candidates with text: "
        f"{evidence.text_candidate_count}"
    )

    for candidate_evidence in evidence.candidates:
        candidate = (
            candidate_evidence.candidate
        )

        print(
            "\n----------------------------------------"
        )

        print(
            f"Candidate: "
            f"{candidate.candidate_no}"
        )

        print(
            f"Source: "
            f"{candidate.source}"
        )

        print(
            f"Rotation selected: "
            f"{candidate_evidence.selected_rotation_degrees}"
        )

        print(
            f"Rotations tested: "
            f"{candidate_evidence.tested_rotations}"
        )

        print(
            f"OCR score: "
            f"{candidate_evidence.ocr_score}"
        )

        print(
            f"From cache: "
            f"{candidate_evidence.from_cache}"
        )

        print(
            f"Image: "
            f"{candidate_evidence.selected_image_path}"
        )

        print(
            "\nSeparate candidate evidence:\n"
        )

        print(
            candidate_evidence.combined_evidence_text
            or "[NO TEXT FOUND]"
        )

    print(
        "\n========== OUTPUT ==========\n"
    )

    print(
        f"Candidate map: "
        f"{evidence.detection.annotated_image_path}"
    )

    print(
        f"Evidence JSON: "
        f"{json_path}"
    )


if __name__ == "__main__":
    main()