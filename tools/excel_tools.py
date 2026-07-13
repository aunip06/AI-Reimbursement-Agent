import pandas as pd


def read_excel_file(file_path):
    """
    Read a reimbursement Excel file.

    Args:
        file_path (str): Path to Excel file.

    Returns:
        pandas.DataFrame
    """

    try:
        df = pd.read_excel(file_path)
        return df

    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None