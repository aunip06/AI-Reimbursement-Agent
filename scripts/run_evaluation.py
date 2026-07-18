r"""
Automated evaluation runner for the AI Reimbursement Agent.

This script:

1. Reads Expected_Status from the test workbook.
2. Runs the complete monthly reimbursement workflow.
3. Compares expected and actual statuses.
4. Detects false approvals and missed approvals.
5. Measures total processing time.
6. Counts OpenAI, cache and local-validation results.
7. Generates an Excel evaluation report.

Example:

python -m scripts.run_evaluation ^
  --excel input\AI_Reimbursement_Smoke_Test.xlsx ^
  --pdf-dir input ^
  --sheet 2026-05_May
"""

import argparse
import time
from pathlib import Path

from copy import copy

import pandas as pd

from tools.report_tool import generate_worksheet_report
from workflow.worksheet_workflow import (
    process_monthly_worksheet,
)


APPROVAL_STATUS = "OK_AUTO_APPROVED"


def normalize_column_name(
    value: object,
) -> str:
    """
    Normalize an Excel column name for reliable lookup.
    """

    return (
        str(value)
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
    )


def normalize_status(
    value: object,
) -> str:
    """
    Normalize an expected or actual status.
    """

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def read_expected_results(
    excel_path: Path,
    worksheet_name: str,
) -> pd.DataFrame:
    """
    Read Expense_ID and Expected_Status from the test workbook.
    """

    dataframe = pd.read_excel(
        excel_path,
        sheet_name=worksheet_name,
        dtype=object,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    required_columns = {
        "Expense_ID",
        "Expected_Status",
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            "The evaluation workbook is missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    expected = dataframe[
        [
            "Expense_ID",
            "Expected_Status",
        ]
    ].copy()

    expected["Expense_ID"] = (
        expected["Expense_ID"]
        .astype(str)
        .str.strip()
    )

    expected["Expected_Status"] = (
        expected["Expected_Status"]
        .apply(normalize_status)
    )

    expected = expected[
        expected["Expense_ID"].ne("")
        & expected["Expense_ID"].ne("nan")
    ].copy()

    duplicate_expense_ids = expected[
        expected["Expense_ID"].duplicated(
            keep=False
        )
    ]

    if not duplicate_expense_ids.empty:
        duplicate_values = sorted(
            duplicate_expense_ids[
                "Expense_ID"
            ].unique()
        )

        raise ValueError(
            "Duplicate Expense_ID values exist in "
            "the expected-result data: "
            + ", ".join(duplicate_values)
        )

    return expected


def build_actual_results_dataframe(
    worksheet_result,
) -> pd.DataFrame:
    """
    Flatten actual workflow results for comparison.
    """

    rows: list[dict[str, object]] = []

    for item in worksheet_result.results:
        rows.append(
            {
                "Expense_ID": (
                    item.claim.expense_id
                ),
                "Actual_Status": normalize_status(
                    item.final_status
                ),
                "Actual_Auto_Payable": (
                    item.auto_payable
                ),
                "Result_Source": (
                    item.result_source
                ),
                "Message": item.message,
                "PDF_Name": (
                    item.claim.monthly_pdf_name
                ),
                "Receipt_Page_No": (
                    item.claim.receipt_page_no
                ),
                "Claimed_Amount": float(
                    item.claim.claimed_amount
                ),
                "Claimed_Vendor": (
                    item.claim.vendor
                ),
            }
        )

    return pd.DataFrame(rows)


def build_comparison_dataframe(
    expected_dataframe: pd.DataFrame,
    actual_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join expected and actual results and calculate test outcomes.
    """

    comparison = expected_dataframe.merge(
        actual_dataframe,
        on="Expense_ID",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    comparison["Expected_Status"] = (
        comparison["Expected_Status"]
        .apply(normalize_status)
    )

    comparison["Actual_Status"] = (
        comparison["Actual_Status"]
        .apply(normalize_status)
    )

    comparison["Expected_Auto_Payable"] = (
        comparison["Expected_Status"]
        == APPROVAL_STATUS
    )

    comparison["Result_Available"] = (
        comparison["_merge"]
        == "both"
    )

    comparison["Status_Correct"] = (
        comparison["Result_Available"]
        & (
            comparison["Expected_Status"]
            == comparison["Actual_Status"]
        )
    )

    comparison["False_Approval"] = (
        comparison["Actual_Auto_Payable"]
        .fillna(False)
        .astype(bool)
        & ~comparison[
            "Expected_Auto_Payable"
        ]
    )

    comparison["Missed_Approval"] = (
        comparison[
            "Expected_Auto_Payable"
        ]
        & ~comparison[
            "Actual_Auto_Payable"
        ]
        .fillna(False)
        .astype(bool)
    )

    comparison["Risk_Level"] = "NORMAL"

    comparison.loc[
        comparison["False_Approval"],
        "Risk_Level",
    ] = "CRITICAL_FALSE_APPROVAL"

    comparison.loc[
        comparison["Missed_Approval"],
        "Risk_Level",
    ] = "MISSED_APPROVAL"

    comparison.loc[
        ~comparison["Result_Available"],
        "Risk_Level",
    ] = "RESULT_MISSING"

    comparison.drop(
        columns=["_merge"],
        inplace=True,
    )

    preferred_columns = [
        "Expense_ID",
        "Expected_Status",
        "Actual_Status",
        "Status_Correct",
        "Expected_Auto_Payable",
        "Actual_Auto_Payable",
        "False_Approval",
        "Missed_Approval",
        "Risk_Level",
        "Result_Source",
        "Claimed_Amount",
        "Claimed_Vendor",
        "PDF_Name",
        "Receipt_Page_No",
        "Message",
        "Result_Available",
    ]

    return comparison[
        preferred_columns
    ]


def create_metrics_dataframe(
    comparison: pd.DataFrame,
    worksheet_result,
    elapsed_seconds: float,
) -> pd.DataFrame:
    """
    Calculate reliability, accuracy, cost-control and runtime metrics.
    """

    total_cases = len(comparison)

    correct_cases = int(
        comparison["Status_Correct"].sum()
    )

    incorrect_cases = (
        total_cases - correct_cases
    )

    accuracy_percentage = (
        round(
            (
                correct_cases
                / total_cases
                * 100
            ),
            2,
        )
        if total_cases
        else 0.0
    )

    false_approvals = int(
        comparison["False_Approval"].sum()
    )

    missed_approvals = int(
        comparison["Missed_Approval"].sum()
    )

    openai_results = sum(
        item.result_source == "openai"
        for item in worksheet_result.results
    )

    cache_results = sum(
        item.result_source == "cache"
        for item in worksheet_result.results
    )

    local_results = sum(
        item.result_source
        == "local_validation"
        for item in worksheet_result.results
    )

    average_seconds = (
        round(
            elapsed_seconds
            / total_cases,
            3,
        )
        if total_cases
        else 0.0
    )

    expected_approvals = int(
        comparison[
            "Expected_Auto_Payable"
        ].sum()
    )

    actual_approvals = int(
        comparison[
            "Actual_Auto_Payable"
        ]
        .fillna(False)
        .sum()
    )

    metrics = [
        {
            "Metric": "Total evaluation cases",
            "Value": total_cases,
        },
        {
            "Metric": "Correct final statuses",
            "Value": correct_cases,
        },
        {
            "Metric": "Incorrect final statuses",
            "Value": incorrect_cases,
        },
        {
            "Metric": "Status accuracy percentage",
            "Value": accuracy_percentage,
        },
        {
            "Metric": "False approvals",
            "Value": false_approvals,
        },
        {
            "Metric": "Missed approvals",
            "Value": missed_approvals,
        },
        {
            "Metric": "Expected approvals",
            "Value": expected_approvals,
        },
        {
            "Metric": "Actual approvals",
            "Value": actual_approvals,
        },
        {
            "Metric": "OpenAI results",
            "Value": openai_results,
        },
        {
            "Metric": "Cached results",
            "Value": cache_results,
        },
        {
            "Metric": "Local validation results",
            "Value": local_results,
        },
        {
            "Metric": "Excel validation errors",
            "Value": len(
                worksheet_result.excel_errors
            ),
        },
        {
            "Metric": "Total processing seconds",
            "Value": round(
                elapsed_seconds,
                3,
            ),
        },
        {
            "Metric": "Average seconds per case",
            "Value": average_seconds,
        },
        {
            "Metric": "Approved claims",
            "Value": (
                worksheet_result.approved_count
            ),
        },
        {
            "Metric": "Exception claims",
            "Value": (
                worksheet_result.exception_count
            ),
        },
        {
            "Metric": "Duplicate-page claims",
            "Value": (
                worksheet_result
                .duplicate_page_claims
            ),
        },
    ]

    return pd.DataFrame(metrics)


def generate_evaluation_report(
    metrics_dataframe: pd.DataFrame,
    comparison_dataframe: pd.DataFrame,
    excel_errors: list[dict],
    output_path: Path,
) -> Path:
    """
    Generate a dedicated evaluation Excel workbook.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    failed_cases = comparison_dataframe[
        comparison_dataframe[
            "Status_Correct"
        ]
        == False
    ].copy()

    false_approvals = comparison_dataframe[
        comparison_dataframe[
            "False_Approval"
        ]
        == True
    ].copy()

    excel_errors_dataframe = pd.DataFrame(
        excel_errors
    )

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
    ) as writer:
        metrics_dataframe.to_excel(
            writer,
            sheet_name="Evaluation_Metrics",
            index=False,
        )

        comparison_dataframe.to_excel(
            writer,
            sheet_name="Status_Comparison",
            index=False,
        )

        failed_cases.to_excel(
            writer,
            sheet_name="Failed_Cases",
            index=False,
        )

        false_approvals.to_excel(
            writer,
            sheet_name="False_Approvals",
            index=False,
        )

        excel_errors_dataframe.to_excel(
            writer,
            sheet_name="Excel_Errors",
            index=False,
        )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

        for cell in worksheet[1]:
            header_font = copy(
                cell.font
                )

            header_font.bold = True
            header_font.color = "FFFFFFFF"

            cell.font = header_font

            header_fill = copy(
                cell.fill
                )

            header_fill.fill_type = "solid"
            header_fill.fgColor.rgb = "FF1F4E78"

            cell.fill = header_fill

            for column_cells in worksheet.columns:
                maximum_length = max(
                    (
                        len(str(cell.value))
                        if cell.value is not None
                        else 0
                    )
                    for cell in column_cells
                )

                column_letter = (
                    column_cells[0]
                    .column_letter
                )

                worksheet.column_dimensions[
                    column_letter
                ].width = min(
                    max(
                        maximum_length + 2,
                        12,
                    ),
                    45,
                )

    return output_path


def print_console_summary(
    metrics_dataframe: pd.DataFrame,
    comparison_dataframe: pd.DataFrame,
) -> None:
    """
    Display the important evaluation results.
    """

    metric_map = dict(
        zip(
            metrics_dataframe["Metric"],
            metrics_dataframe["Value"],
        )
    )

    print(
        "\n========== EVALUATION SUMMARY ==========\n"
    )

    print(
        "Total cases: "
        f"{metric_map['Total evaluation cases']}"
    )

    print(
        "Correct statuses: "
        f"{metric_map['Correct final statuses']}"
    )

    print(
        "Incorrect statuses: "
        f"{metric_map['Incorrect final statuses']}"
    )

    print(
        "Accuracy: "
        f"{metric_map['Status accuracy percentage']}%"
    )

    print(
        "False approvals: "
        f"{metric_map['False approvals']}"
    )

    print(
        "Missed approvals: "
        f"{metric_map['Missed approvals']}"
    )

    print(
        "OpenAI results: "
        f"{metric_map['OpenAI results']}"
    )

    print(
        "Cache results: "
        f"{metric_map['Cached results']}"
    )

    print(
        "Local validation results: "
        f"{metric_map['Local validation results']}"
    )

    print(
        "Total processing time: "
        f"{metric_map['Total processing seconds']} seconds"
    )

    incorrect = comparison_dataframe[
        comparison_dataframe[
            "Status_Correct"
        ]
        == False
    ]

    if incorrect.empty:
        print(
            "\nAll expected statuses matched."
        )
    else:
        print(
            "\n========== INCORRECT CASES ==========\n"
        )

        for _, row in incorrect.iterrows():
            print(
                f"{row['Expense_ID']}: "
                f"expected={row['Expected_Status']} | "
                f"actual={row['Actual_Status']} | "
                f"source={row['Result_Source']}"
            )


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line options.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the AI reimbursement workflow "
            "against expected test statuses."
        )
    )

    parser.add_argument(
        "--excel",
        required=True,
        help="Path to the test Excel workbook.",
    )

    parser.add_argument(
        "--pdf-dir",
        required=True,
        help="Directory containing monthly PDFs.",
    )

    parser.add_argument(
        "--sheet",
        default="2026-05_May",
        help="Worksheet to evaluate.",
    )

    parser.add_argument(
        "--output-dir",
        default="output/evaluation",
        help="Directory for evaluation reports.",
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

    output_directory = Path(
        arguments.output_dir
    )

    if not excel_path.exists():
        raise FileNotFoundError(
            f"Excel file not found: {excel_path}"
        )

    if not pdf_directory.exists():
        raise FileNotFoundError(
            f"PDF directory not found: {pdf_directory}"
        )

    print(
        "\n========== EVALUATION INPUT ==========\n"
    )

    print(f"Excel: {excel_path}")
    print(f"Worksheet: {arguments.sheet}")
    print(f"PDF directory: {pdf_directory}")

    expected_dataframe = (
        read_expected_results(
            excel_path=excel_path,
            worksheet_name=arguments.sheet,
        )
    )

    start_time = time.perf_counter()

    worksheet_result = (
        process_monthly_worksheet(
            excel_path=excel_path,
            worksheet_name=arguments.sheet,
            pdf_directory=pdf_directory,
        )
    )

    elapsed_seconds = (
        time.perf_counter()
        - start_time
    )

    actual_dataframe = (
        build_actual_results_dataframe(
            worksheet_result
        )
    )

    comparison_dataframe = (
        build_comparison_dataframe(
            expected_dataframe=expected_dataframe,
            actual_dataframe=actual_dataframe,
        )
    )

    metrics_dataframe = (
        create_metrics_dataframe(
            comparison=comparison_dataframe,
            worksheet_result=worksheet_result,
            elapsed_seconds=elapsed_seconds,
        )
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    evaluation_path = (
        output_directory
        / (
            f"{excel_path.stem}"
            "_evaluation.xlsx"
        )
    )

    monthly_report_path = (
        output_directory
        / (
            f"{excel_path.stem}"
            "_reimbursement_report.xlsx"
        )
    )

    generate_evaluation_report(
        metrics_dataframe=metrics_dataframe,
        comparison_dataframe=comparison_dataframe,
        excel_errors=(
            worksheet_result.excel_errors
        ),
        output_path=evaluation_path,
    )

    generate_worksheet_report(
        worksheet_result=worksheet_result,
        output_path=monthly_report_path,
    )

    print_console_summary(
        metrics_dataframe=metrics_dataframe,
        comparison_dataframe=comparison_dataframe,
    )

    print(
        "\n========== GENERATED REPORTS ==========\n"
    )

    print(
        f"Evaluation report: {evaluation_path}"
    )

    print(
        f"Reimbursement report: {monthly_report_path}"
    )


if __name__ == "__main__":
    main()