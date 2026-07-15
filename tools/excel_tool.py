from pathlib import Path
from typing import Any

import pandas as pd


def read_excel_file(
    file_path: str | Path,
    sheet_name: str | int | None = 0,
):
    """
    Read an Excel file using pandas.

    Args:
        file_path:
            Path to the Excel workbook.

        sheet_name:
            0 or another number:
                Read a worksheet by position.

            "SheetName":
                Read a worksheet by name.

            None:
                Read all worksheets and return a dictionary.

    Returns:
        A pandas DataFrame when one worksheet is selected.

        A dictionary of DataFrames when sheet_name=None.

        None when the workbook cannot be read.
    """

    try:
        return pd.read_excel(
            file_path,
            sheet_name=sheet_name,
        )

    except Exception as error:
        print(f"Error reading Excel file: {error}")
        return None


def read_expense_sheet(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Read the current reimbursement expense-sheet format.

    This function supports the existing workbook structure
    containing month headings, expense rows, and total rows.
    """

    try:
        dataframe = pd.read_excel(
            file_path,
            header=None,
        )

    except Exception as error:
        print(f"Error reading expense sheet: {error}")
        return []

    expenses: list[dict[str, Any]] = []
    current_month = None

    for row in dataframe.values:
        row = list(row)

        # Ensure the row contains at least five columns.
        while len(row) < 5:
            row.append(None)

        first_cell = row[0]
        description_cell = row[2]

        # Detect the current month heading.
        # This rule is temporary and will later be replaced
        # by the final 12-worksheet employee workbook format.
        if (
            isinstance(first_cell, str)
            and "2026" in first_cell
        ):
            current_month = first_cell.strip()
            continue

        # Skip the table heading row.
        if str(first_cell).strip().lower() == "no":
            continue

        # Skip the total row.
        if str(description_cell).strip().lower() == "total":
            continue

        # Skip empty rows.
        if pd.isna(first_cell):
            continue

        expense = {
            "month": current_month,
            "date": row[1],
            "description": row[2],
            "amount": row[3],
            "remarks": row[4],
        }

        expenses.append(expense)

    return expenses
