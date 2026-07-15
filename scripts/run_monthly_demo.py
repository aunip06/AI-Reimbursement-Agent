"""
Run every valid claim in one monthly worksheet and
generate the final reimbursement Excel report.
"""

from pathlib import Path

from tools.report_tool import (
    generate_worksheet_report,
)
from workflow.worksheet_workflow import (
    process_monthly_worksheet,
)


EXCEL_PATH = Path(
    r"input\reimbursement_claims_FY2026_27_template.xlsx"
)

WORKSHEET_NAME = "2026-05_May"

PDF_DIRECTORY = Path("input")

REPORT_PATH = Path(
    "output"
) / "monthly_reports" / (
    f"{WORKSHEET_NAME}_reimbursement_report.xlsx"
)


def main() -> None:
    print("\n========== MONTHLY PROCESSING ==========\n")
    print(f"Excel file: {EXCEL_PATH}")
    print(f"Worksheet: {WORKSHEET_NAME}")
    print(f"PDF directory: {PDF_DIRECTORY}")

    result = process_monthly_worksheet(
        excel_path=EXCEL_PATH,
        worksheet_name=WORKSHEET_NAME,
        pdf_directory=PDF_DIRECTORY,
    )

    print("\n========== MONTHLY SUMMARY ==========\n")
    print(f"Total claims: {result.total_claims}")
    print(f"Completed claims: {result.completed_claims}")
    print(f"Approved claims: {result.approved_count}")
    print(f"Exception claims: {result.exception_count}")
    print(
        "Duplicate-page claims: "
        f"{result.duplicate_page_claims}"
    )
    print(
        f"Excel errors: "
        f"{len(result.excel_errors)}"
    )

    print("\n========== CLAIM RESULTS ==========\n")

    for claim_result in result.results:
        print(
            f"{claim_result.claim.expense_id}: "
            f"{claim_result.final_status} | "
            f"source={claim_result.result_source} | "
            f"auto_payable={claim_result.auto_payable}"
        )

    report_path = generate_worksheet_report(
        worksheet_result=result,
        output_path=REPORT_PATH,
    )

    print("\n========== REPORT ==========\n")
    print(f"Report created: {report_path}")


if __name__ == "__main__":
    main()