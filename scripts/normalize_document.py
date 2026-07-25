from __future__ import annotations

import argparse
from pathlib import Path

from tools.document_ingestion_tool import (
    normalize_document_to_pdf,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize a supported document into PDF."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "PDF, Word, PowerPoint, Excel, image, "
            "or another supported document."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=(
            "output/document_ingestion"
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    result = normalize_document_to_pdf(
        source_file=Path(
            arguments.input
        ),
        output_directory=Path(
            arguments.output_dir
        ),
    )

    print(
        "\n========== DOCUMENT INGESTION ==========\n"
    )

    print(
        result.model_dump_json(
            indent=2
        )
    )

    print(
        "\n========== SUMMARY ==========\n"
    )

    print(
        f"Status: {result.status}"
    )

    print(
        f"Family: {result.source_family}"
    )

    print(
        f"Converter: {result.converter}"
    )

    print(
        f"Pages: {result.page_count}"
    )

    print(
        "Normalized PDF: "
        f"{result.normalized_pdf_path}"
    )


if __name__ == "__main__":
    main()