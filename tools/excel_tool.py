import pandas as pd


def read_expenses(file_path, month):
    # Read the Excel without assuming headers
    df = pd.read_excel(
        file_path,
        sheet_name="Expenses",
        header=None
    )

    start_row = None

    # Find the selected month
    for index, row in df.iterrows():
        if str(row[0]).strip() == month:
            start_row = index + 2   # Skip month row and header row
            break

    if start_row is None:
        raise ValueError(f"Month '{month}' not found.")

    expenses = []

    # Read rows until blank row
    for i in range(start_row, len(df)):

        if pd.isna(df.iloc[i, 0]):
            break

        expenses.append({
            "No": df.iloc[i, 0],
            "Date": df.iloc[i, 1],
            "Description": df.iloc[i, 2],
            "Amount": df.iloc[i, 3],
            "Remarks": df.iloc[i, 4],
        })

    return pd.DataFrame(expenses)