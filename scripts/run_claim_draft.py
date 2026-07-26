"""Generate a reimbursement claim draft from one or more documents."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.claim_draft_report_tool import write_claim_draft_workbook
from workflow.pdf_intake_workflow import process_document_intake


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Detect receipts in one or more documents and generate "
            "a pre-filled reimbursement claim-draft workbook."
        )
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="One or more PDFs or supported documents.",
    )
    parser.add_argument(
        "--output",
        default=(
            "output/claim_drafts/"
            "reimbursement_claim_draft.xlsx"
        ),
        help="Output .xlsx path.",
    )
    parser.add_argument(
        "--intake-output-dir",
        default="output/pdf_intake",
        help="Existing document-intake output directory.",
    )
    return parser.parse_args()


def main() -> None:
    """Run intake for all input files and create one combined draft."""

    arguments = parse_arguments()
    results = []

    for input_value in arguments.input:
        source_path = Path(input_value)

        print(
            f"Processing: {source_path}"
        )

        result = process_document_intake(
            source_file=source_path,
            output_root=arguments.intake_output_dir,
        )
        results.append(result)

    output_path = write_claim_draft_workbook(
        results=results,
        output_path=arguments.output,
    )

    print(
        "\n========== CLAIM DRAFT GENERATED ==========\n"
    )
    print(
        f"Documents: {len(results)}"
    )
    print(
        "Pages: "
        + str(
            sum(
                result.total_pages
                for result in results
            )
        )
    )
    print(
        "Candidates: "
        + str(
            sum(
                result.total_candidates
                for result in results
            )
        )
    )
    print(
        f"Workbook: {output_path}"
    )


if __name__ == "__main__":
    main()
