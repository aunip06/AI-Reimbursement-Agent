from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st
from agents.exceptions import (
    AgentsException,
    MaxTurnsExceeded,
    ModelBehaviorError,
    ModelRefusalError,
)

from tools.excel_tool import (
    list_worksheet_names,
    read_claims_from_worksheet,
)
from tools.report_tool import (
    build_result_rows,
    generate_worksheet_report,
)
from workflow.worksheet_workflow import (
    process_monthly_worksheet,
)


PROJECT_ROOT = Path(__file__).resolve().parent
TEMP_ROOT = PROJECT_ROOT / "temp" / "streamlit_uploads"
REPORT_ROOT = PROJECT_ROOT / "output" / "streamlit_reports"


def initialize_session() -> None:
    """
    Create a separate temporary directory for the current
    Streamlit browser session.
    """

    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid4().hex

    if "worksheet_result" not in st.session_state:
        st.session_state.worksheet_result = None

    if "report_bytes" not in st.session_state:
        st.session_state.report_bytes = None

    if "report_name" not in st.session_state:
        st.session_state.report_name = None


def get_session_directory() -> Path:
    """
    Return the current Streamlit session directory.
    """

    session_directory = (
        TEMP_ROOT
        / st.session_state.session_id
    )

    session_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return session_directory


def save_uploaded_file(
    uploaded_file,
    destination_directory: Path,
) -> Path:
    """
    Save one Streamlit uploaded file safely.

    Path(uploaded_file.name).name removes any directory
    components supplied by the browser.
    """

    destination_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_file_name = Path(
        uploaded_file.name
    ).name

    destination_path = (
        destination_directory
        / safe_file_name
    )

    destination_path.write_bytes(
        uploaded_file.getvalue()
    )

    return destination_path


def claims_to_dataframe(
    claims,
) -> pd.DataFrame:
    """
    Convert validated Claim objects into a preview table.
    """

    return pd.DataFrame(
        [
            claim.model_dump(
                mode="json"
            )
            for claim in claims
        ]
    )


def display_summary(
    worksheet_result,
) -> None:
    """
    Display the main verification metrics.
    """

    openai_count = sum(
        item.result_source == "openai"
        for item in worksheet_result.results
    )

    cache_count = sum(
        item.result_source == "cache"
        for item in worksheet_result.results
    )

    local_count = sum(
        item.result_source == "local_validation"
        for item in worksheet_result.results
    )

    first_row = st.columns(4)

    first_row[0].metric(
        "Total Claims",
        worksheet_result.total_claims,
    )

    first_row[1].metric(
        "Approved",
        worksheet_result.approved_count,
    )

    first_row[2].metric(
        "Exceptions",
        worksheet_result.exception_count,
    )

    first_row[3].metric(
        "Duplicate Pages",
        worksheet_result.duplicate_page_claims,
    )

    second_row = st.columns(3)

    second_row[0].metric(
        "OpenAI Analyses",
        openai_count,
    )

    second_row[1].metric(
        "Cached Analyses",
        cache_count,
    )

    second_row[2].metric(
        "Local Validations",
        local_count,
    )


def display_claim_details(
    worksheet_result,
) -> None:
    """
    Display claim-level decisions and page evidence.
    """

    for item in worksheet_result.results:
        title = (
            f"{item.claim.expense_id} — "
            f"{item.final_status}"
        )

        with st.expander(title):
            detail_columns = st.columns(3)

            detail_columns[0].write(
                f"**Claimed amount:** "
                f"{item.claim.claimed_amount}"
            )

            detail_columns[1].write(
                f"**Vendor:** "
                f"{item.claim.vendor}"
            )

            detail_columns[2].write(
                f"**PDF page:** "
                f"{item.claim.receipt_page_no}"
            )

            st.write(
                f"**Result source:** "
                f"{item.result_source}"
            )

            st.write(
                f"**Auto payable:** "
                f"{item.auto_payable}"
            )

            st.write(
                f"**Message:** "
                f"{item.message}"
            )

            workflow_result = (
                item.workflow_result
            )

            if workflow_result is None:
                continue

            evidence = (
                workflow_result.evidence
            )

            st.write(
                f"**Evidence status:** "
                f"{evidence.status}"
            )

            if (
                evidence.image_path
                and Path(
                    evidence.image_path
                ).exists()
            ):
                st.image(
                    evidence.image_path,
                    caption=(
                        f"{evidence.pdf_file_name}, "
                        f"page {evidence.page_number}"
                    ),
                )

            processing_result = (
                workflow_result.processing_result
            )

            if processing_result is None:
                continue

            analysis = (
                processing_result.analysis
            )

            decision = (
                processing_result.final_decision
            )

            st.write(
                "**Extracted receipt evidence**"
            )

            st.json(
                analysis.receipt.model_dump(
                    mode="json"
                )
            )

            st.write(
                "**Agent comparison**"
            )

            st.json(
                {
                    "amount_match": (
                        analysis.amount_match
                    ),
                    "date_match": (
                        analysis.date_match
                    ),
                    "vendor_match": (
                        analysis.vendor_match
                    ),
                    "description_supported": (
                        analysis.description_supported
                    ),
                    "payment_mode_match": (
                        analysis.payment_mode_match
                    ),
                    "transaction_id_match": (
                        analysis.transaction_id_match
                    ),
                    "invoice_no_match": (
                        analysis.invoice_no_match
                    ),
                    "recommended_status": (
                        analysis.recommended_status
                    ),
                    "analysis_confidence": (
                        analysis.analysis_confidence
                    ),
                    "reasons": (
                        analysis.reasons
                    ),
                }
            )

            st.write(
                "**Final safety checks**"
            )

            st.json(
                decision.safety_checks
            )


def main() -> None:
    st.set_page_config(
        page_title=(
            "AI Reimbursement Verification"
        ),
        page_icon="🧾",
        layout="wide",
    )

    initialize_session()

    st.title(
        "AI Reimbursement Verification"
    )

    st.caption(
        "Local OCR + OpenAI Agents SDK + "
        "page-level evidence verification"
    )

    st.info(
        "Uncached valid claims can make one OpenAI analysis "
        "request each. Repeated identical claims use the local cache."
    )

    st.subheader("1. Upload employee files")

    excel_upload = st.file_uploader(
        "Employee reimbursement Excel workbook",
        type=["xlsx"],
        accept_multiple_files=False,
    )

    pdf_uploads = st.file_uploader(
        "Monthly reimbursement PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if excel_upload is None:
        st.warning(
            "Upload an employee Excel workbook to continue."
        )
        return

    session_directory = (
        get_session_directory()
    )

    excel_directory = (
        session_directory
        / "excel"
    )

    pdf_directory = (
        session_directory
        / "monthly_pdfs"
    )

    excel_path = save_uploaded_file(
        uploaded_file=excel_upload,
        destination_directory=excel_directory,
    )

    for pdf_upload in pdf_uploads:
        save_uploaded_file(
            uploaded_file=pdf_upload,
            destination_directory=pdf_directory,
        )

    worksheet_names = list_worksheet_names(
        excel_path
    )

    if not worksheet_names:
        st.error(
            "No readable worksheets were found in the workbook."
        )
        return

    st.subheader("2. Select worksheet")

    worksheet_name = st.selectbox(
        "Monthly worksheet",
        options=worksheet_names,
    )

    claims, excel_errors = (
        read_claims_from_worksheet(
            file_path=excel_path,
            worksheet_name=worksheet_name,
        )
    )

    st.subheader("3. Validate Excel claims")

    preview_columns = st.columns(3)

    preview_columns[0].metric(
        "Valid Claims",
        len(claims),
    )

    preview_columns[1].metric(
        "Excel Errors",
        len(excel_errors),
    )

    preview_columns[2].metric(
        "Uploaded PDFs",
        len(pdf_uploads),
    )

    if claims:
        st.write("**Validated claim preview**")

        st.dataframe(
            claims_to_dataframe(claims),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "No valid claims were found in the selected worksheet."
        )

    if excel_errors:
        st.write("**Excel validation errors**")

        st.dataframe(
            pd.DataFrame(excel_errors),
            use_container_width=True,
            hide_index=True,
        )

    missing_pdf_names = sorted(
        {
            claim.monthly_pdf_name
            for claim in claims
            if not (
                pdf_directory
                / claim.monthly_pdf_name
            ).exists()
        }
    )

    if missing_pdf_names:
        st.warning(
            "The following referenced PDFs have not been uploaded:\n\n"
            + "\n".join(
                f"- {file_name}"
                for file_name in missing_pdf_names
            )
        )

    run_disabled = (
        not claims
        or not pdf_uploads
    )

    run_clicked = st.button(
        "Run Reimbursement Verification",
        type="primary",
        disabled=run_disabled,
    )

    if run_clicked:
        st.session_state.worksheet_result = None
        st.session_state.report_bytes = None
        st.session_state.report_name = None

        try:
            with st.spinner(
                "Running OCR, SDK analysis and safety checks..."
            ):
                worksheet_result = (
                    process_monthly_worksheet(
                        excel_path=excel_path,
                        worksheet_name=worksheet_name,
                        pdf_directory=pdf_directory,
                    )
                )

                safe_worksheet_name = (
                    worksheet_name
                    .replace("/", "-")
                    .replace("\\", "-")
                )

                report_name = (
                    f"{safe_worksheet_name}"
                    "_reimbursement_report.xlsx"
                )

                report_path = (
                    REPORT_ROOT
                    / st.session_state.session_id
                    / report_name
                )

                generated_report = (
                    generate_worksheet_report(
                        worksheet_result=worksheet_result,
                        output_path=report_path,
                    )
                )

                st.session_state.worksheet_result = (
                    worksheet_result
                )

                st.session_state.report_bytes = (
                    generated_report.read_bytes()
                )

                st.session_state.report_name = (
                    report_name
                )

        except MaxTurnsExceeded:
            st.error(
                "The SDK agent exceeded its configured turn limit."
            )

        except ModelRefusalError:
            st.error(
                "The model refused a reimbursement analysis request."
            )

        except ModelBehaviorError:
            st.error(
                "The model returned invalid structured output."
            )

        except AgentsException as error:
            st.error(
                "An OpenAI Agents SDK error occurred."
            )

            st.code(
                f"{type(error).__name__}: {error}"
            )

        except Exception as error:
            st.error(
                "The verification workflow failed."
            )

            st.exception(error)

    worksheet_result = (
        st.session_state.worksheet_result
    )

    if worksheet_result is None:
        return

    st.success(
        "Reimbursement verification completed."
    )

    st.subheader("4. Verification summary")

    display_summary(
        worksheet_result
    )

    result_rows = build_result_rows(
        worksheet_result
    )

    results_dataframe = pd.DataFrame(
        result_rows
    )

    st.subheader("5. Complete results")

    st.dataframe(
        results_dataframe,
        use_container_width=True,
        hide_index=True,
    )

    approved_dataframe = (
        results_dataframe[
            results_dataframe[
                "Auto_Payable"
            ]
            == True
        ]
        if not results_dataframe.empty
        else pd.DataFrame()
    )

    exception_dataframe = (
        results_dataframe[
            results_dataframe[
                "Auto_Payable"
            ]
            == False
        ]
        if not results_dataframe.empty
        else pd.DataFrame()
    )

    approved_tab, exception_tab = st.tabs(
        [
            "Approved for Accounts",
            "Exception Report",
        ]
    )

    with approved_tab:
        if approved_dataframe.empty:
            st.info(
                "No claims were approved."
            )
        else:
            st.dataframe(
                approved_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    with exception_tab:
        if exception_dataframe.empty:
            st.info(
                "No exception claims were found."
            )
        else:
            st.dataframe(
                exception_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    st.subheader("6. Claim evidence")

    display_claim_details(
        worksheet_result
    )

    st.subheader("7. Download report")

    st.download_button(
        label="Download Final Excel Report",
        data=st.session_state.report_bytes,
        file_name=st.session_state.report_name,
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        type="primary",
    )


if __name__ == "__main__":
    main()