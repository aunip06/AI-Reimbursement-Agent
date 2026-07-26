"""Validate a user-completed reimbursement claim-draft workbook."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.claim_draft_report_tool import validate_completed_claim_draft


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate Claim_Draft values against the workbook's "
            "Evidence_Register."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Completed claim-draft .xlsx file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional validated output .xlsx path.",
    )
    return parser.parse_args()


def main() -> None:
    """Validate the workbook and print status counts."""

    arguments = parse_arguments()
    output_path, validation_rows = validate_completed_claim_draft(
        input_workbook=Path(
            arguments.input
        ),
        output_path=(
            Path(arguments.output)
            if arguments.output
            else None
        ),
    )

    counts: dict[str, int] = {}

    for row in validation_rows:
        status = row[
            "Validation_Status"
        ]
        counts[status] = (
            counts.get(status, 0)
            + 1
        )

    print(
        "\n========== CLAIM DRAFT VALIDATION ==========\n"
    )

    for status, count in sorted(
        counts.items()
    ):
        print(
            f"{status}: {count}"
        )

    print(
        f"\nValidated workbook: {output_path}"
    )


if __name__ == "__main__":
    main()
