import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from models.claim import Claim


REQUIRED_CLAIM_COLUMNS = [
    "Expense_ID",
    "Employee_ID",
    "Employee_Name",
    "First_Name",
    "Surname",
    "Expense_Date",
    "Expense_Category",
    "Description",
    "Claimed_Amount",
    "Vendor",
    "Payment_Mode",
    "Monthly_PDF_Name",
    "Receipt_Page_No",
]


OPTIONAL_CLAIM_COLUMNS = [
    "Transaction_ID",
    "Invoice_No",
    "Remarks",
]


PAYMENT_MODE_ALIASES = {
    "upi": "upi",
    "gpay": "upi",
    "google pay": "upi",
    "phonepe": "upi",
    "phone pay": "upi",
    "phonepay": "upi",
    "paytm": "upi",
    "paytm upi": "upi",
    "bhim": "upi",
    "cash": "cash",
    "card": "card",
    "credit card": "card",
    "debit card": "card",
    "wallet": "wallet",
    "bank transfer": "bank_transfer",
    "bank-transfer": "bank_transfer",
    "bank_transfer": "bank_transfer",
    "net banking": "bank_transfer",
    "neft": "bank_transfer",
    "rtgs": "bank_transfer",
    "imps": "bank_transfer",
}


def read_excel_file(
    file_path: str | Path,
    sheet_name: str | int | None = 0,
):
    """
    Read one worksheet or all worksheets from an Excel workbook.
    """

    try:
        return pd.read_excel(
            file_path,
            sheet_name=sheet_name,
        )

    except Exception as error:
        print(f"Error reading Excel file: {error}")
        return None


def list_worksheet_names(
    file_path: str | Path,
) -> list[str]:
    """
    Return the worksheet names available in an Excel workbook.
    """

    workbook_path = Path(file_path)

    if not workbook_path.exists():
        return []

    try:
        excel_file = pd.ExcelFile(workbook_path)

    except Exception as error:
        print(f"Error reading workbook structure: {error}")
        return []

    return excel_file.sheet_names


def read_expense_sheet(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Read the existing legacy expense workbook.

    This function is retained only for compatibility with the
    current Expenses worksheet containing month-heading rows.
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
    current_month: str | None = None

    month_pattern = re.compile(
        r"^[A-Za-z]+[-\s]\d{4}$"
    )

    for row in dataframe.values:
        row = list(row)

        while len(row) < 5:
            row.append(None)

        first_cell = row[0]
        description_cell = row[2]

        if isinstance(first_cell, str):
            cleaned_first_cell = first_cell.strip()

            if month_pattern.fullmatch(cleaned_first_cell):
                current_month = cleaned_first_cell
                continue

        if str(first_cell).strip().casefold() == "no":
            continue

        if (
            str(description_cell)
            .strip()
            .casefold()
            == "total"
        ):
            continue

        if is_blank(first_cell):
            continue

        expenses.append(
            {
                "month": current_month,
                "number": first_cell,
                "date": row[1],
                "description": row[2],
                "amount": row[3],
                "remarks": row[4],
            }
        )

    return expenses


def is_blank(value: Any) -> bool:
    """
    Return True for empty Excel values.
    """

    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass

    return not str(value).strip()


def normalize_required_text(
    value: Any,
) -> str:
    """
    Normalize a mandatory text field.
    """

    if is_blank(value):
        return ""

    return str(value).strip()


def normalize_optional_text(
    value: Any,
) -> str | None:
    """
    Normalize an optional text field.
    """

    if is_blank(value):
        return None

    text = str(value).strip()

    return text or None


def normalize_date(
    value: Any,
):
    """
    Convert an Excel date into a Python date.
    """

    if is_blank(value):
        return None

    parsed_date = pd.to_datetime(
        value,
        dayfirst=True,
        errors="coerce",
    )

    if pd.isna(parsed_date):
        return None

    return parsed_date.date()


def normalize_amount(
    value: Any,
) -> Decimal | None:
    """
    Convert an Excel amount into a two-decimal Decimal.
    """

    if is_blank(value):
        return None

    cleaned_value = (
        str(value)
        .replace("₹", "")
        .replace(",", "")
        .strip()
    )

    try:
        amount = Decimal(cleaned_value)

    except (InvalidOperation, ValueError):
        return None

    return amount.quantize(
        Decimal("0.01")
    )


def normalize_page_number(
    value: Any,
) -> int | None:
    """
    Convert a page number into a positive integer.
    """

    if is_blank(value):
        return None

    try:
        numeric_value = float(value)

    except (TypeError, ValueError):
        return None

    if not numeric_value.is_integer():
        return None

    page_number = int(numeric_value)

    if page_number < 1:
        return None

    return page_number


def normalize_payment_mode(
    value: Any,
) -> str:
    """
    Convert common payment-mode names into canonical values.
    """

    payment_mode = normalize_required_text(
        value
    ).casefold()

    if not payment_mode:
        return "unknown"

    return PAYMENT_MODE_ALIASES.get(
        payment_mode,
        payment_mode,
    )


def format_validation_error(
    validation_error: ValidationError,
) -> str:
    """
    Convert Pydantic validation errors into readable messages.
    """

    messages: list[str] = []

    for error in validation_error.errors():
        field_name = ".".join(
            str(part)
            for part in error["loc"]
        )

        messages.append(
            f"{field_name}: {error['msg']}"
        )

    return "; ".join(messages)


def make_excel_error(
    worksheet_name: str,
    source_row_number: int | None,
    expense_id: str | None,
    reason: str,
) -> dict[str, Any]:
    """
    Create a consistent Excel import error record.
    """

    return {
        "worksheet_name": worksheet_name,
        "source_row_number": source_row_number,
        "expense_id": expense_id,
        "status": "FORMAT_ERROR",
        "reason": reason,
    }


def read_claims_from_worksheet(
    file_path: str | Path,
    worksheet_name: str,
) -> tuple[list[Claim], list[dict[str, Any]]]:
    """
    Read one final-format monthly worksheet.

    Returns:
        Valid Claim objects.
        Excel import and validation errors.
    """

    workbook_path = Path(file_path)

    if not workbook_path.exists():
        return [], [
            make_excel_error(
                worksheet_name=worksheet_name,
                source_row_number=None,
                expense_id=None,
                reason=(
                    f"Excel workbook does not exist: "
                    f"{workbook_path}"
                ),
            )
        ]

    try:
        dataframe = pd.read_excel(
            workbook_path,
            sheet_name=worksheet_name,
        )

    except Exception as error:
        return [], [
            make_excel_error(
                worksheet_name=worksheet_name,
                source_row_number=None,
                expense_id=None,
                reason=(
                    f"Could not read worksheet: {error}"
                ),
            )
        ]

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    missing_columns = [
        column
        for column in REQUIRED_CLAIM_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        return [], [
            make_excel_error(
                worksheet_name=worksheet_name,
                source_row_number=None,
                expense_id=None,
                reason=(
                    "Missing required columns: "
                    + ", ".join(missing_columns)
                ),
            )
        ]

    claims: list[Claim] = []
    errors: list[dict[str, Any]] = []

    seen_expense_ids: set[str] = set()
    
    for dataframe_index, row in dataframe.iterrows():
        source_row_number = dataframe_index + 2

        row_has_data = any(
            not is_blank(row.get(column))
            for column in REQUIRED_CLAIM_COLUMNS
            + OPTIONAL_CLAIM_COLUMNS
        )

        if not row_has_data:
            continue

        expense_id = normalize_required_text(
            row.get("Expense_ID")
        )

        claim_data = {
            "expense_id": expense_id,
            "employee_id": normalize_required_text(
                row.get("Employee_ID")
            ),
            "employee_name": normalize_required_text(
                row.get("Employee_Name")
            ),
            "first_name": normalize_required_text(
                row.get("First_Name")
            ),
            "surname": normalize_required_text(
                row.get("Surname")
            ),
            "expense_date": normalize_date(
                row.get("Expense_Date")
            ),
            "expense_category": normalize_required_text(
                row.get("Expense_Category")
            ),
            "description": normalize_required_text(
                row.get("Description")
            ),
            "claimed_amount": normalize_amount(
                row.get("Claimed_Amount")
            ),
            "vendor": normalize_required_text(
                row.get("Vendor")
            ),
            "payment_mode": normalize_payment_mode(
                row.get("Payment_Mode")
            ),
            "transaction_id": normalize_optional_text(
                row.get("Transaction_ID")
            ),
            "invoice_no": normalize_optional_text(
                row.get("Invoice_No")
            ),
            "monthly_pdf_name": normalize_required_text(
                row.get("Monthly_PDF_Name")
            ),
            "receipt_page_no": normalize_page_number(
                row.get("Receipt_Page_No")
            ),
            "remarks": normalize_optional_text(
                row.get("Remarks")
            ),
            "worksheet_name": worksheet_name,
            "source_row_number": source_row_number,
        }

        row_errors: list[str] = []

        try:
            claim = Claim(**claim_data)

        except ValidationError as error:
            row_errors.append(
                format_validation_error(error)
            )
            claim = None

        if expense_id:
            if expense_id in seen_expense_ids:
                row_errors.append(
                    "Duplicate Expense_ID found."
                )
            else:
                seen_expense_ids.add(expense_id)

        
        if row_errors:
            errors.append(
                make_excel_error(
                    worksheet_name=worksheet_name,
                    source_row_number=source_row_number,
                    expense_id=expense_id or None,
                    reason="; ".join(row_errors),
                )
            )
            continue

        if claim is not None:
            claims.append(claim)

    return claims, errors