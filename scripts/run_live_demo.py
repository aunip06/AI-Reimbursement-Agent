"""
Manual controlled live SDK test.

The first run can make one OpenAI request.
Later identical runs should use the local claim-aware cache.
"""

from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    ModelBehaviorError,
    ModelRefusalError,
)

from tools.excel_tool import read_claims_from_worksheet
from workflow.end_to_end_workflow import (
    process_claim_from_files,
)


EXCEL_FILE = (
    r"input\reimbursement_claims_FY2026_27_template.xlsx"
)

WORKSHEET_NAME = "2026-05_May"

PDF_DIRECTORY = r"input"


def main() -> None:
    claims, excel_errors = read_claims_from_worksheet(
        file_path=EXCEL_FILE,
        worksheet_name=WORKSHEET_NAME,
    )

    if excel_errors:
        print("\n========== EXCEL ERRORS ==========\n")

        for error in excel_errors:
            print(error)

    if not claims:
        raise RuntimeError(
            "No valid claims were found in the selected worksheet."
        )

    # Use a fixed live-test ID.
    #
    # First run:
    #   Normally uses OpenAI.
    #
    # Later identical runs:
    #   Normally use the local cache.
    claim = claims[0].model_copy(
        update={
            "expense_id": (
                "DEMO_EMP001_2026_05_LIVE_CONTROLLED_001"
            ),
        }
    )

    print("\n========== LIVE TEST INPUT ==========\n")
    print(f"Expense ID: {claim.expense_id}")
    print(f"Claimed amount: {claim.claimed_amount}")
    print(f"Claim date: {claim.expense_date}")
    print(f"Claim vendor: {claim.vendor}")
    print(f"PDF: {claim.monthly_pdf_name}")
    print(f"PDF page: {claim.receipt_page_no}")

    try:
        result = process_claim_from_files(
            claim=claim,
            pdf_directory=PDF_DIRECTORY,
            dry_run=False,
        )

    except MaxTurnsExceeded:
        print(
            "\nLIVE TEST ERROR: The agent exceeded "
            "the one-turn limit."
        )
        raise

    except ModelRefusalError:
        print(
            "\nLIVE TEST ERROR: The model refused "
            "the analysis request."
        )
        raise

    except ModelBehaviorError:
        print(
            "\nLIVE TEST ERROR: The model returned invalid "
            "structured output."
        )
        raise

    except AgentsException as error:
        print(
            "\nLIVE TEST ERROR: An Agents SDK error occurred."
        )
        print(f"Error type: {type(error).__name__}")
        raise

    print("\n========== WORKFLOW RESULT ==========\n")
    print(f"Workflow status: {result.workflow_status}")
    print(f"Evidence status: {result.evidence.status}")
    print(f"Evidence image: {result.evidence.image_path}")
    print(f"Workflow message: {result.message}")

    if result.processing_result is None:
        print(
            "\nNo SDK analysis was performed because local "
            "evidence preparation failed."
        )
        return

    processing_result = result.processing_result

    print(
        f"Result source: "
        f"{processing_result.result_source}"
    )

    if processing_result.analysis is not None:
        print("\n========== AGENT ANALYSIS ==========\n")
        print(
            processing_result.analysis.model_dump_json(
                indent=2,
            )
        )

    if processing_result.final_decision is not None:
        decision = processing_result.final_decision

        print("\n========== FINAL SAFETY DECISION ==========\n")
        print(f"Final status: {decision.final_status}")
        print(f"Auto payable: {decision.auto_payable}")

        print("\nSafety checks:")

        for check_name, passed in decision.safety_checks.items():
            print(f"  {check_name}: {passed}")

        print("\nReasons:")

        for reason in decision.reasons:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()