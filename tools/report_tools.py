def generate_report(status, message):
    """
    Generate a reimbursement verification report.

    Args:
        status (str): Verification status.
        message (str): Detailed explanation.

    Returns:
        dict
    """

    report = {
        "status": status,
        "message": message
    }

    return report