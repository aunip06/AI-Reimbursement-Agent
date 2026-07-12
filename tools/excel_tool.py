import pandas as pd


def read_expense_sheet(file_path):

    df = pd.read_excel(file_path, header=None)

    expenses = []

    current_month = None

    for row in df.values:

        row = list(row)

        # Detect month heading
        if isinstance(row[0], str) and "2026" in row[0]:
            current_month = row[0]
            continue

        # Skip header rows
        if row[0] == "No":
            continue

        # Skip totals
        if row[2] == "Total":
            continue

        # Skip empty rows
        if pd.isna(row[0]):
            continue

        expense = {
            "month": current_month,
            "date": row[1],
            "description": row[2],
            "amount": row[3],
            "remarks": row[4]
        }

        expenses.append(expense)

    return expenses