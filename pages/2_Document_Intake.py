from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from tools.pdf_intake_report_tool import build_intake_rows
from workflow.pdf_intake_workflow import process_document_intake


st.set_page_config(
    page_title="Document Intake",
    page_icon="📄",
    layout="wide",
)


SUPPORTED_TYPES = [
    "pdf",
    "doc",
    "docx",
    "docm",
    "dot",
    "dotx",
    "dotm",
    "rtf",
    "txt",
    "odt",
    "html",
    "htm",
    "ppt",
    "pptx",
    "pptm",
    "pps",
    "ppsx",
    "ppsm",
    "odp",
    "xls",
    "xlsx",
    "xlsm",
    "xlsb",
    "csv",
    "ods",
    "jpg",
    "jpeg",
    "png",
    "bmp",
    "tif",
    "tiff",
    "gif",
    "webp",
    "xps",
    "epub",
    "mobi",
    "fb2",
    "cbz",
    "svg",
]

UPLOAD_ROOT = Path("temp/streamlit_document_intake")


def safe_file_name(value: str) -> str:
    name = Path(value).name
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return safe_name or "uploaded_document"


def upload_signature(uploaded_files) -> str:
    digest = hashlib.sha256()

    for uploaded_file in uploaded_files or []:
        digest.update(uploaded_file.name.encode("utf-8"))
        digest.update(str(uploaded_file.size).encode("ascii"))

    return digest.hexdigest()


def save_uploaded_files(uploaded_files) -> list[Path]:
    signature = upload_signature(uploaded_files)
    upload_directory = UPLOAD_ROOT / signature[:16]
    upload_directory.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []

    for uploaded_file in uploaded_files:
        destination = upload_directory / safe_file_name(uploaded_file.name)
        destination.write_bytes(uploaded_file.getvalue())
        saved_paths.append(destination)

    return saved_paths


def result_rows_dataframe(results) -> pd.DataFrame:
    rows: list[dict] = []

    for result in results:
        rows.extend(build_intake_rows(result))

    return pd.DataFrame(rows)


st.title("Document-Only Receipt Intake")

st.caption(
    "Upload PDFs, Office files, images, or other supported documents. "
    "Every detected bill is cropped, OCR-processed, and extracted independently."
)

st.info(
    "This mode extracts receipt records from documents. It does not approve "
    "reimbursement because no independent Excel claim is being compared."
)

uploaded_files = st.file_uploader(
    "Upload one or more documents",
    type=SUPPORTED_TYPES,
    accept_multiple_files=True,
    help=(
        "Maximum supported input size is 100 MB per file. Password-protected "
        "or unsupported documents are blocked."
    ),
)

current_signature = upload_signature(uploaded_files)

if (
    st.session_state.get("document_intake_upload_signature")
    != current_signature
):
    st.session_state["document_intake_upload_signature"] = current_signature
    st.session_state.pop("document_intake_results", None)

action_columns = st.columns([1, 1, 4])

run_clicked = action_columns[0].button(
    "Extract Receipts",
    type="primary",
    disabled=not uploaded_files,
    use_container_width=True,
)

clear_clicked = action_columns[1].button(
    "Clear Results",
    use_container_width=True,
)

if clear_clicked:
    st.session_state.pop("document_intake_results", None)
    st.rerun()

if run_clicked:
    saved_paths = save_uploaded_files(uploaded_files)
    progress_bar = st.progress(0)
    status_area = st.empty()
    results = []

    for index, saved_path in enumerate(saved_paths, start=1):
        status_area.info(
            f"Processing {saved_path.name} ({index}/{len(saved_paths)})..."
        )

        result = process_document_intake(
            source_file=saved_path,
            output_root="output/pdf_intake",
        )

        results.append(result)
        progress_bar.progress(index / len(saved_paths))

    status_area.success("Document intake completed.")
    st.session_state["document_intake_results"] = results


results = st.session_state.get("document_intake_results", [])

if results:
    total_documents = len(results)
    total_pages = sum(result.total_pages for result in results)
    total_candidates = sum(result.total_candidates for result in results)
    total_ready = sum(result.extracted_count for result in results)
    total_exceptions = sum(result.exception_count for result in results)
    total_duplicates = sum(result.duplicate_count for result in results)

    metric_columns = st.columns(6)
    metric_columns[0].metric("Documents", total_documents)
    metric_columns[1].metric("Pages", total_pages)
    metric_columns[2].metric("Candidates", total_candidates)
    metric_columns[3].metric("Extracted Ready", total_ready)
    metric_columns[4].metric("Exceptions", total_exceptions)
    metric_columns[5].metric("Duplicates", total_duplicates)

    results_tab, evidence_tab, downloads_tab = st.tabs(
        [
            "Extraction Results",
            "Receipt Evidence",
            "Downloads",
        ]
    )

    with results_tab:
        result_dataframe = result_rows_dataframe(results)

        if result_dataframe.empty:
            st.warning("No receipt candidates were produced.")
        else:
            preferred_columns = [
                "Generated_ID",
                "Source_File",
                "Page_Number",
                "Candidate_Number",
                "Intake_Status",
                "Date",
                "Amount",
                "Currency",
                "Remark",
                "Merchant",
                "Payment_Mode",
                "Transaction_ID",
                "Invoice_No",
                "Extraction_Confidence",
                "Result_Source",
                "Message",
            ]

            visible_columns = [
                column
                for column in preferred_columns
                if column in result_dataframe.columns
            ]

            st.dataframe(
                result_dataframe[visible_columns],
                use_container_width=True,
                hide_index=True,
            )

    with evidence_tab:
        selectable_items = [
            item
            for result in results
            for item in result.items
        ]

        if not selectable_items:
            st.info("No evidence items are available.")
        else:
            item_by_id = {
                item.generated_id: item
                for item in selectable_items
            }

            selected_id = st.selectbox(
                "Select a receipt or page result",
                options=list(item_by_id),
            )

            selected_item = item_by_id[selected_id]
            status_columns = st.columns(4)
            status_columns[0].metric("Status", selected_item.status)
            status_columns[1].metric("Page", selected_item.page_number)
            status_columns[2].metric(
                "Candidate",
                (
                    selected_item.candidate_no
                    if selected_item.candidate_no is not None
                    else "None"
                ),
            )
            status_columns[3].metric("Source", selected_item.result_source)

            st.info(selected_item.message)

            image_column, data_column = st.columns([1, 1])

            with image_column:
                if (
                    selected_item.candidate_map_image_path
                    and Path(selected_item.candidate_map_image_path).exists()
                ):
                    st.image(
                        selected_item.candidate_map_image_path,
                        caption="Page candidate map",
                        use_container_width=True,
                    )

                if (
                    selected_item.candidate_image_path
                    and Path(selected_item.candidate_image_path).exists()
                ):
                    st.image(
                        selected_item.candidate_image_path,
                        caption="Isolated bill candidate",
                        use_container_width=True,
                    )

            with data_column:
                if selected_item.receipt:
                    receipt_data = selected_item.receipt.model_dump(mode="json")
                    receipt_dataframe = pd.DataFrame(
                        [
                            {"Field": key, "Value": value}
                            for key, value in receipt_data.items()
                        ]
                    )

                    st.dataframe(
                        receipt_dataframe,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "No structured receipt extraction is available for this item."
                    )

            with st.expander("OCR evidence"):
                if selected_item.ocr_text:
                    st.code(selected_item.ocr_text, language=None)
                else:
                    st.info("No OCR text is available.")

    with downloads_tab:
        for result_index, result in enumerate(results, start=1):
            st.markdown(f"**{result.ingestion.source_file_name}**")
            st.write(result.message)
            download_columns = st.columns(2)

            if result.report_path and Path(result.report_path).exists():
                report_path = Path(result.report_path)

                download_columns[0].download_button(
                    "Download Excel Report",
                    data=report_path.read_bytes(),
                    file_name=report_path.name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    key=f"intake_excel_{result_index}",
                    use_container_width=True,
                )

            if result.json_path and Path(result.json_path).exists():
                json_path = Path(result.json_path)

                download_columns[1].download_button(
                    "Download JSON Report",
                    data=json_path.read_bytes(),
                    file_name=json_path.name,
                    mime="application/json",
                    key=f"intake_json_{result_index}",
                    use_container_width=True,
                )

            st.divider()
