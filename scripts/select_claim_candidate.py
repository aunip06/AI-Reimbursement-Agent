"""
Select one independent receipt candidate for one Excel claim.

This script runs in shadow mode and does not change the
production reimbursement workflow.
"""

import argparse
from pathlib import Path

from tools.excel_tool import (
    read_claims_from_worksheet,
)
from tools.pdf_tool import (
    render_pdf_page,
)
from workflow.candidate_selection_workflow import (
    select_candidate_for_claim,
)
from workflow.receipt_candidate_evidence_workflow import (
    prepare_page_candidate_evidence,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select one receipt candidate for one claim."
        )
    )

    parser.add_argument(
        "--excel",
        required=True,
    )

    parser.add_argument(
        "--sheet",
        required=True,
    )

    parser.add_argument(
        "--expense-id",
        required=True,
    )

    parser.add_argument(
        "--pdf-dir",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        default=(
            "output/candidate_selection"
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    excel_path = Path(
        arguments.excel
    )

    pdf_directory = Path(
        arguments.pdf_dir
    )

    claims, errors = (
        read_claims_from_worksheet(
            file_path=excel_path,
            worksheet_name=(
                arguments.sheet
            ),
        )
    )

    if errors:
        print(
            "Excel validation errors:"
        )

        for error in errors:
            print(error)

    matching_claims = [
        claim
        for claim in claims
        if (
            claim.expense_id
            == arguments.expense_id
        )
    ]

    if not matching_claims:
        raise ValueError(
            "Expense_ID was not found among "
            "the valid worksheet claims."
        )

    claim = matching_claims[0]

    pdf_path = (
        pdf_directory
        / claim.monthly_pdf_name
    )

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    rendered_page = render_pdf_page(
        pdf_path=pdf_path,
        page_number=(
            claim.receipt_page_no
        ),
    )

    page_output_directory = (
        Path(
            arguments.output_dir
        )
        / claim.expense_id
    )

    page_evidence = (
        prepare_page_candidate_evidence(
            pdf_path=pdf_path,
            page_number=(
                claim.receipt_page_no
            ),
            rendered_image_path=(
                rendered_page.image_path
            ),
            output_directory=(
                page_output_directory
                / "evidence"
            ),
        )
    )

    selection = (
        select_candidate_for_claim(
            claim=claim,
            page_evidence=(
                page_evidence
            ),
        )
    )

    output_path = (
        page_output_directory
        / "candidate_selection.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        selection.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        "\n========== CANDIDATE SELECTION ==========\n"
    )

    print(
        f"Expense ID: {selection.expense_id}"
    )

    print(
        f"PDF page: {selection.page_number}"
    )

    print(
        f"Selection status: {selection.status}"
    )

    print(
        "Selected candidate: "
        f"{selection.selected_candidate_no}"
    )

    for evaluation in (
        selection.candidate_evaluations
    ):
        print(
            "\n----------------------------------------"
        )

        print(
            f"Candidate: "
            f"{evaluation.candidate_no}"
        )

        print(
            f"Local score: "
            f"{evaluation.local_score}"
        )

        print(
            f"Shortlisted: "
            f"{evaluation.shortlisted}"
        )

        print(
            f"Semantic score: "
            f"{evaluation.semantic_score}"
        )

        print(
            f"Strict match: "
            f"{evaluation.strict_match}"
        )

        if evaluation.analysis:
            print(
                "Agent status: "
                f"{evaluation.analysis.recommended_status}"
            )

            print(
                "Agent confidence: "
                f"{evaluation.analysis.analysis_confidence}"
            )

    print(
        "\nReasons:"
    )

    for reason in selection.reasons:
        print(
            f"- {reason}"
        )

    print(
        f"\nSelection JSON: {output_path}"
    )


if __name__ == "__main__":
    main()