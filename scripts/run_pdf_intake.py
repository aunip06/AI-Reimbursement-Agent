from __future__ import annotations

import argparse
from pathlib import Path

from workflow.pdf_intake_workflow import process_document_intake


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract all independent bills from one supported document."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "PDF, Office document, image, or another supported document."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="output/pdf_intake",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    result = process_document_intake(
        source_file=Path(arguments.input),
        output_root=Path(arguments.output_dir),
    )

    print("\n========== DOCUMENT INTAKE SUMMARY ==========\n")
    print(f"Input status: {result.ingestion.status}")
    print(f"Input family: {result.ingestion.source_family}")
    print(f"Pages: {result.total_pages}")
    print(f"Candidates: {result.total_candidates}")
    print(f"Extracted ready: {result.extracted_count}")
    print(f"Exceptions: {result.exception_count}")
    print(f"Duplicates: {result.duplicate_count}")

    for item in result.items:
        receipt = item.receipt

        print("\n----------------------------------------")
        print(f"{item.generated_id}: {item.status}")
        print(f"Page/Candidate: {item.page_number}/{item.candidate_no}")
        print(f"Date: {receipt.date if receipt else None}")
        print(f"Amount: {receipt.amount if receipt else None}")
        print(
            "Remark: "
            f"{getattr(receipt, 'remark', None) if receipt else None}"
        )
        print(f"Merchant: {receipt.merchant if receipt else None}")
        print(f"Source: {item.result_source}")
        print(f"Message: {item.message}")

    print("\n========== OUTPUTS ==========\n")
    print(f"Excel report: {result.report_path}")
    print(f"JSON report: {result.json_path}")


if __name__ == "__main__":
    main()
