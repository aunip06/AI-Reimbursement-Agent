"""Streamlit page for PDF-first reimbursement claim creation and validation."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from tools.claim_draft_report_tool import (
    build_claim_draft_rows,
    build_evidence_rows,
    validate_completed_claim_draft,
    write_claim_draft_workbook,
)
from workflow.pdf_intake_workflow import process_document_intake


st.set_page_config(
    page_title="PDF to Claim Draft",
    page_icon="🧾",
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

UPLOAD_ROOT = Path(
    "temp/streamlit_claim_draft"
)
OUTPUT_ROOT = Path(
    "output/claim_drafts"
)


def safe_file_name(value: str) -> str:
    """Remove unsafe characters while retaining a useful filename."""

    name = Path(value).name
    safe_name = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        name,
    ).strip("._")

    return safe_name or "uploaded_document"


def upload_signature(uploaded_files) -> str:
    """Create a stable session signature without storing file contents."""

    digest = hashlib.sha256()

    for uploaded_file in uploaded_files or []:
        digest.update(
            uploaded_file.name.encode(
                "utf-8"
            )
        )
        digest.update(
            str(
                uploaded_file.size
            ).encode("ascii")
        )

    return digest.hexdigest()


def save_uploaded_files(
    uploaded_files,
    folder_name: str,
) -> list[Path]:
    """Save uploaded files in one isolated session directory."""

    signature = upload_signature(
        uploaded_files
    )
    directory = (
        UPLOAD_ROOT
        / folder_name
        / signature[:16]
    )
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths: list[Path] = []

    for uploaded_file in uploaded_files:
        path = directory / safe_file_name(
            uploaded_file.name
        )
        path.write_bytes(
            uploaded_file.getvalue()
        )
        paths.append(path)

    return paths


st.title(
    "PDF → Reimbursement Claim Draft"
)

st.caption(
    "Detect every independent receipt, extract its evidence, create one Excel "
    "row per receipt, collect missing business information, and validate the "
    "completed draft against locked evidence."
)

st.info(
    "This workflow creates and validates a reimbursement draft. "
    "It does not transfer money or directly approve payment."
)

generate_tab, validate_tab = st.tabs(
    [
        "1. Generate Draft from Documents",
        "2. Validate Completed Draft",
    ]
)

with generate_tab:
    st.subheader(
        "Generate a pre-filled claim workbook"
    )

    st.write(
        "Upload one or more documents. The existing document-intake pipeline "
        "normalises each file, detects independent receipt candidates, runs "
        "OCR, uses the configured OpenAI Receipt Extraction Agent when the "
        "cache does not contain the result, and returns structured evidence."
    )

    uploaded_documents = st.file_uploader(
        "Upload receipt PDFs or supported documents",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        key="claim_draft_source_documents",
    )

    current_signature = upload_signature(
        uploaded_documents
    )

    if (
        st.session_state.get(
            "claim_draft_source_signature"
        )
        != current_signature
    ):
        st.session_state[
            "claim_draft_source_signature"
        ] = current_signature
        st.session_state.pop(
            "claim_draft_results",
            None,
        )
        st.session_state.pop(
            "claim_draft_workbook_path",
            None,
        )

    run_clicked = st.button(
        "Detect Receipts and Generate Claim Draft",
        type="primary",
        disabled=not uploaded_documents,
        use_container_width=True,
    )

    if run_clicked:
        saved_paths = save_uploaded_files(
            uploaded_documents,
            "source_documents",
        )
        progress = st.progress(0)
        status = st.empty()
        results = []

        for index, source_path in enumerate(
            saved_paths,
            start=1,
        ):
            status.info(
                f"Processing {source_path.name} "
                f"({index}/{len(saved_paths)})..."
            )

            result = process_document_intake(
                source_file=source_path,
                output_root="output/pdf_intake",
            )
            results.append(result)
            progress.progress(
                index / len(saved_paths)
            )

        combined_signature = upload_signature(
            uploaded_documents
        )[:16]
        workbook_path = (
            OUTPUT_ROOT
            / combined_signature
            / "reimbursement_claim_draft.xlsx"
        )

        write_claim_draft_workbook(
            results=results,
            output_path=workbook_path,
        )

        st.session_state[
            "claim_draft_results"
        ] = results
        st.session_state[
            "claim_draft_workbook_path"
        ] = str(workbook_path)

        status.success(
            "Claim draft workbook generated."
        )

    results = st.session_state.get(
        "claim_draft_results",
        [],
    )
    workbook_path_value = st.session_state.get(
        "claim_draft_workbook_path"
    )

    if results and workbook_path_value:
        claim_rows = build_claim_draft_rows(
            results
        )
        evidence_rows = build_evidence_rows(
            results
        )

        total_pages = sum(
            result.total_pages
            for result in results
        )
        total_candidates = sum(
            result.total_candidates
            for result in results
        )
        duplicate_count = sum(
            row["Draft_Status"]
            == "DUPLICATE_RECEIPT"
            for row in claim_rows
        )

        metric_columns = st.columns(5)
        metric_columns[0].metric(
            "Documents",
            len(results),
        )
        metric_columns[1].metric(
            "Pages",
            total_pages,
        )
        metric_columns[2].metric(
            "Candidates",
            total_candidates,
        )
        metric_columns[3].metric(
            "Draft Rows",
            len(claim_rows),
        )
        metric_columns[4].metric(
            "Duplicates",
            duplicate_count,
        )

        preview_tab, evidence_tab, download_tab = st.tabs(
            [
                "Claim Draft Preview",
                "Evidence Register",
                "Download",
            ]
        )

        with preview_tab:
            if claim_rows:
                preview = pd.DataFrame(
                    claim_rows
                )
                visible_columns = [
                    "No",
                    "Receipt_ID",
                    "Month",
                    "Extracted_Date",
                    "Claimed_Date",
                    "Extracted_Amount",
                    "Claimed_Amount",
                    "Merchant_Payee",
                    "Extracted_Remark",
                    "Expense_Category",
                    "Business_Purpose",
                    "Employee_Name",
                    "User_Confirmation",
                    "Manager_Approval",
                    "Draft_Status",
                    "Source_PDF",
                    "Page_No",
                    "Candidate_No",
                ]

                st.dataframe(
                    preview[
                        [
                            column
                            for column in visible_columns
                            if column in preview.columns
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning(
                    "No valid receipt rows were available for the claim draft."
                )

        with evidence_tab:
            if evidence_rows:
                st.dataframe(
                    pd.DataFrame(
                        evidence_rows
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "No evidence records are available."
                )

        with download_tab:
            workbook_path = Path(
                workbook_path_value
            )

            if workbook_path.exists():
                st.download_button(
                    "Download Reimbursement Claim Draft",
                    data=workbook_path.read_bytes(),
                    file_name=workbook_path.name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )

                st.success(
                    "Open Claim_Draft, complete the yellow columns, set "
                    "User_Confirmation, obtain Manager_Approval, save the file, "
                    "then upload it in the second tab."
                )

with validate_tab:
    st.subheader(
        "Validate a completed claim draft"
    )

    st.write(
        "Validation uses Receipt_ID to compare the editable Claim_Draft values "
        "with the protected Evidence_Register. It blocks missing business data, "
        "changed date/amount, duplicates, rejected rows, and pending approvals."
    )

    completed_workbook = st.file_uploader(
        "Upload the completed claim-draft workbook",
        type=["xlsx"],
        accept_multiple_files=False,
        key="completed_claim_draft",
    )

    validate_clicked = st.button(
        "Validate Completed Draft",
        type="primary",
        disabled=completed_workbook is None,
        use_container_width=True,
    )

    if validate_clicked and completed_workbook:
        saved_path = save_uploaded_files(
            [completed_workbook],
            "completed_drafts",
        )[0]
        validated_output = (
            OUTPUT_ROOT
            / "validated"
            / (
                saved_path.stem
                + "_validated.xlsx"
            )
        )

        try:
            (
                validated_path,
                validation_rows,
            ) = validate_completed_claim_draft(
                input_workbook=saved_path,
                output_path=validated_output,
            )
        except Exception as error:
            st.error(
                f"Validation failed: {error}"
            )
        else:
            st.session_state[
                "validated_claim_draft_path"
            ] = str(validated_path)
            st.session_state[
                "claim_draft_validation_rows"
            ] = validation_rows

    validation_rows = st.session_state.get(
        "claim_draft_validation_rows",
        [],
    )
    validated_path_value = st.session_state.get(
        "validated_claim_draft_path"
    )

    if validation_rows and validated_path_value:
        validation_dataframe = pd.DataFrame(
            validation_rows
        )
        status_counts = (
            validation_dataframe[
                "Validation_Status"
            ]
            .value_counts()
            .to_dict()
        )

        metrics = st.columns(4)
        metrics[0].metric(
            "Rows",
            len(validation_rows),
        )
        metrics[1].metric(
            "Verified",
            status_counts.get(
                "OK_VERIFIED",
                0,
            ),
        )
        metrics[2].metric(
            "Pending",
            sum(
                count
                for status, count in status_counts.items()
                if "PENDING" in status
            ),
        )
        metrics[3].metric(
            "Blocked",
            sum(
                count
                for status, count in status_counts.items()
                if status != "OK_VERIFIED"
                and "PENDING" not in status
            ),
        )

        st.dataframe(
            validation_dataframe,
            use_container_width=True,
            hide_index=True,
        )

        validated_path = Path(
            validated_path_value
        )

        if validated_path.exists():
            st.download_button(
                "Download Validated Claim Workbook",
                data=validated_path.read_bytes(),
                file_name=validated_path.name,
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
