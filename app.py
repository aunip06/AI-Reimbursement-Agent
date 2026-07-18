from __future__ import annotations

import hashlib
import html
import time
from pathlib import Path
from typing import Any
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


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

TEMP_ROOT = (
    PROJECT_ROOT
    / "temp"
    / "streamlit_uploads"
)

REPORT_ROOT = (
    PROJECT_ROOT
    / "output"
    / "streamlit_reports"
)

APPROVAL_STATUS = "OK_AUTO_APPROVED"


STATUS_LABELS = {
    "OK_AUTO_APPROVED": "Auto Approved",
    "BILL_NOT_FOUND_ON_PAGE": "Bill Not Found",
    "OCR_UNCLEAR": "OCR Unclear",
    "AMOUNT_MISMATCH": "Amount Mismatch",
    "DATE_MISMATCH": "Date Mismatch",
    "VENDOR_MISMATCH": "Vendor Mismatch",
    "TRANSACTION_ID_MISMATCH": "Transaction ID Mismatch",
    "INVOICE_NO_MISMATCH": "Invoice Number Mismatch",
    "POSSIBLE_MATCH_NOT_APPROVED": "Possible Match — Blocked",
    "DUPLICATE_PAGE_REFERENCE": "Duplicate Page Reference",
    "PDF_MISSING": "PDF Missing",
    "PAGE_MISSING": "Page Missing",
}


STATUS_GROUPS = {
    "OK_AUTO_APPROVED": "approved",

    "DUPLICATE_PAGE_REFERENCE": "duplicate",

    "PDF_MISSING": "missing",
    "PAGE_MISSING": "missing",
    "BILL_NOT_FOUND_ON_PAGE": "missing",

    "OCR_UNCLEAR": "unclear",
    "POSSIBLE_MATCH_NOT_APPROVED": "unclear",

    "AMOUNT_MISMATCH": "mismatch",
    "DATE_MISMATCH": "mismatch",
    "VENDOR_MISMATCH": "mismatch",
    "TRANSACTION_ID_MISMATCH": "mismatch",
    "INVOICE_NO_MISMATCH": "mismatch",
}


# ============================================================
# PAGE STYLE
# ============================================================

def inject_application_styles() -> None:
    """
    Apply professional styling that remains readable in both
    Streamlit light mode and dark mode.
    """

    st.markdown(
        """
        <style>
        /* =====================================================
           MAIN PAGE
        ===================================================== */

        .block-container {
            max-width: 1500px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }

        /* =====================================================
           HEADER
        ===================================================== */

        .main-header {
            padding: 1.4rem 1.6rem;
            border-radius: 16px;
            background:
                linear-gradient(
                    120deg,
                    #12263a 0%,
                    #1f4e78 58%,
                    #2f75b5 100%
                );
            margin-bottom: 1rem;
            box-shadow:
                0 8px 24px rgba(18, 38, 58, 0.16);
        }

        .main-header,
        .main-header * {
            color: #ffffff !important;
        }

        .main-header h1 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.25;
        }

        .main-header p {
            margin-top: 0.55rem;
            margin-bottom: 0;
            opacity: 0.95;
            font-size: 1rem;
        }

        /* =====================================================
           WORKFLOW STRIP
        ===================================================== */

        .workflow-strip {
            padding: 0.9rem 1rem;
            border: 1px solid #d9e2f3;
            border-radius: 12px;
            background: #f7faff;
            margin-bottom: 1.2rem;
        }

        .workflow-strip,
        .workflow-strip * {
            color: #1e293b !important;
        }

        /* =====================================================
           STREAMLIT METRIC CARDS
        ===================================================== */

        div[data-testid="stMetric"] {
            background: #ffffff !important;
            border: 1px solid #dbe3ed !important;
            padding: 1rem !important;
            border-radius: 14px !important;
            box-shadow:
                0 4px 14px rgba(15, 23, 42, 0.08);
            min-height: 125px;
        }

        div[data-testid="stMetric"] * {
            color: #0f172a !important;
        }

        div[data-testid="stMetricLabel"] {
            color: #475569 !important;
        }

        div[data-testid="stMetricLabel"] * {
            color: #475569 !important;
            font-weight: 600 !important;
        }

        div[data-testid="stMetricValue"] {
            color: #0f172a !important;
        }

        div[data-testid="stMetricValue"] * {
            color: #0f172a !important;
            font-weight: 700 !important;
        }

        div[data-testid="stMetricDelta"] * {
            color: #334155 !important;
        }

        /* =====================================================
           STREAMLIT ALERTS
           st.success, st.info, st.warning and st.error
        ===================================================== */

        div[data-testid="stAlert"] {
            border-radius: 12px !important;
        }

        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] span,
        div[data-testid="stAlert"] div,
        div[data-testid="stAlert"] strong {
            color: #172033 !important;
        }

        div[data-testid="stNotification"] p,
        div[data-testid="stNotification"] span,
        div[data-testid="stNotification"] div,
        div[data-testid="stNotification"] strong {
            color: #172033 !important;
        }

        /* =====================================================
           CUSTOM GENERAL CARDS
        ===================================================== */

        .section-card {
            border: 1px solid #dbe3ed;
            border-radius: 14px;
            padding: 1rem;
            background: #ffffff;
            margin-bottom: 1rem;
            box-shadow:
                0 3px 12px rgba(15, 23, 42, 0.06);
        }

        .section-card,
        .section-card * {
            color: #0f172a !important;
        }

        .small-muted {
            color: #64748b !important;
            font-size: 0.88rem;
        }

        /* =====================================================
           PAYMENT DECISION CARDS
        ===================================================== */

        .decision-approved {
            padding: 1rem;
            border-radius: 12px;
            background: #ecfdf3;
            border: 1px solid #86efac;
            border-left: 6px solid #22c55e;
        }

        .decision-approved,
        .decision-approved * {
            color: #14532d !important;
        }

        .decision-blocked {
            padding: 1rem;
            border-radius: 12px;
            background: #fff7ed;
            border: 1px solid #fdba74;
            border-left: 6px solid #f97316;
        }

        .decision-blocked,
        .decision-blocked * {
            color: #7c2d12 !important;
        }

        /* =====================================================
           STATUS BADGES
        ===================================================== */

        .status-badge {
            display: inline-block;
            padding: 0.3rem 0.72rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            margin-bottom: 0.5rem;
        }

        .status-approved {
            color: #166534 !important;
            background: #dcfce7;
            border: 1px solid #86efac;
        }

        .status-mismatch {
            color: #991b1b !important;
            background: #fee2e2;
            border: 1px solid #fca5a5;
        }

        .status-missing {
            color: #92400e !important;
            background: #fef3c7;
            border: 1px solid #fcd34d;
        }

        .status-unclear {
            color: #6b21a8 !important;
            background: #f3e8ff;
            border: 1px solid #d8b4fe;
        }

        .status-duplicate {
            color: #9a3412 !important;
            background: #ffedd5;
            border: 1px solid #fdba74;
        }

        .status-default {
            color: #334155 !important;
            background: #e2e8f0;
            border: 1px solid #cbd5e1;
        }

        /* =====================================================
           EXPANDERS
        ===================================================== */

        div[data-testid="stExpander"] {
            border-radius: 12px !important;
        }

        /* =====================================================
           BUTTONS
        ===================================================== */

        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stDownloadButton"] button[kind="primary"] {
            background: #1f4e78 !important;
            color: #ffffff !important;
            border: 1px solid #1f4e78 !important;
            font-weight: 700 !important;
        }

        div[data-testid="stButton"] button[kind="primary"] *,
        div[data-testid="stDownloadButton"] button[kind="primary"] * {
            color: #ffffff !important;
        }

        /* =====================================================
           DATAFRAMES
        ===================================================== */

        div[data-testid="stDataFrame"] {
            border: 1px solid #dbe3ed;
            border-radius: 10px;
            overflow: hidden;
        }

        /* =====================================================
           SIDEBAR
        ===================================================== */

        section[data-testid="stSidebar"] {
            border-right: 1px solid #334155;
        }

        /* =====================================================
           LIGHT CONTENT INSIDE CUSTOM HTML
        ===================================================== */

        .light-surface {
            background: #ffffff;
            border: 1px solid #dbe3ed;
            border-radius: 12px;
            padding: 1rem;
        }

        .light-surface,
        .light-surface * {
            color: #0f172a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# SESSION MANAGEMENT
# ============================================================

def initialize_session() -> None:
    """
    Initialize all persistent Streamlit session values.
    """

    defaults = {
        "session_id": uuid4().hex,
        "worksheet_result": None,
        "report_bytes": None,
        "report_name": None,
        "processing_seconds": None,
        "processed_input_signature": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_processed_results() -> None:
    """
    Clear only generated results while preserving uploads.
    """

    st.session_state.worksheet_result = None
    st.session_state.report_bytes = None
    st.session_state.report_name = None
    st.session_state.processing_seconds = None
    st.session_state.processed_input_signature = None


def get_session_directory() -> Path:
    """
    Return the active browser-session storage directory.
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


# ============================================================
# FILE MANAGEMENT
# ============================================================

def safe_uploaded_name(
    file_name: str,
) -> str:
    """
    Remove path components from an uploaded filename.
    """

    return Path(file_name).name


def save_uploaded_file(
    uploaded_file,
    destination_directory: Path,
) -> Path:
    """
    Save one uploaded file into the session directory.
    """

    destination_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination_path = (
        destination_directory
        / safe_uploaded_name(
            uploaded_file.name
        )
    )

    destination_path.write_bytes(
        uploaded_file.getvalue()
    )

    return destination_path


def synchronize_uploaded_pdfs(
    pdf_uploads,
    pdf_directory: Path,
) -> list[Path]:
    """
    Keep the session PDF directory synchronized with
    the PDFs currently selected in the uploader.

    Removed uploads are also removed from the active session.
    """

    pdf_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    desired_names = {
        safe_uploaded_name(
            uploaded_file.name
        ).casefold()
        for uploaded_file in pdf_uploads
    }

    for existing_pdf in pdf_directory.glob(
        "*.pdf"
    ):
        if (
            existing_pdf.name.casefold()
            not in desired_names
        ):
            existing_pdf.unlink(
                missing_ok=True
            )

    saved_paths: list[Path] = []

    for uploaded_file in pdf_uploads:
        saved_paths.append(
            save_uploaded_file(
                uploaded_file=uploaded_file,
                destination_directory=(
                    pdf_directory
                ),
            )
        )

    return saved_paths


def build_input_signature(
    excel_upload,
    pdf_uploads,
    worksheet_name: str,
) -> str:
    """
    Build a content-based signature for the complete
    processing input.

    This prevents results from an older upload or worksheet
    from being displayed after inputs change.
    """

    digest = hashlib.sha256()

    digest.update(
        worksheet_name.encode(
            "utf-8"
        )
    )

    digest.update(
        safe_uploaded_name(
            excel_upload.name
        ).encode(
            "utf-8"
        )
    )

    digest.update(
        excel_upload.getvalue()
    )

    sorted_pdfs = sorted(
        pdf_uploads,
        key=lambda uploaded_file: (
            safe_uploaded_name(
                uploaded_file.name
            ).casefold()
        ),
    )

    for uploaded_file in sorted_pdfs:
        digest.update(
            safe_uploaded_name(
                uploaded_file.name
            ).encode(
                "utf-8"
            )
        )

        digest.update(
            uploaded_file.getvalue()
        )

    return digest.hexdigest()


# ============================================================
# DATA PREPARATION
# ============================================================

def claims_to_dataframe(
    claims,
) -> pd.DataFrame:
    """
    Create a concise, business-readable claim preview.
    """

    rows: list[dict[str, Any]] = []

    for claim in claims:
        rows.append(
            {
                "Expense ID": claim.expense_id,
                "Employee": claim.employee_name,
                "Date": claim.expense_date,
                "Category": claim.expense_category,
                "Description": claim.description,
                "Amount": float(
                    claim.claimed_amount
                ),
                "Vendor": claim.vendor,
                "Payment Mode": (
                    claim.payment_mode
                ),
                "PDF": (
                    claim.monthly_pdf_name
                ),
                "Page": (
                    claim.receipt_page_no
                ),
            }
        )

    return pd.DataFrame(rows)


def build_pdf_readiness_dataframe(
    claims,
    pdf_directory: Path,
) -> pd.DataFrame:
    """
    Display whether every PDF referenced by the claims
    is currently available.
    """

    pdf_to_claims: dict[str, list[str]] = {}

    for claim in claims:
        pdf_to_claims.setdefault(
            claim.monthly_pdf_name,
            [],
        ).append(
            claim.expense_id
        )

    rows: list[dict[str, Any]] = []

    for pdf_name, expense_ids in sorted(
        pdf_to_claims.items()
    ):
        pdf_path = (
            pdf_directory
            / pdf_name
        )

        rows.append(
            {
                "Referenced PDF": pdf_name,
                "Available": pdf_path.exists(),
                "Claims": len(
                    expense_ids
                ),
                "Expense IDs": ", ".join(
                    expense_ids
                ),
            }
        )

    return pd.DataFrame(rows)


def normalize_header_name(
    value: object,
) -> str:
    """
    Normalize optional evaluation columns.
    """

    return (
        str(value)
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
    )


def read_expected_statuses(
    excel_path: Path,
    worksheet_name: str,
) -> dict[str, str]:
    """
    Read Expected_Status when using an evaluation workbook.

    Normal employee workbooks do not need this column.
    """

    try:
        dataframe = pd.read_excel(
            excel_path,
            sheet_name=worksheet_name,
            dtype=object,
        )

    except Exception:
        return {}

    dataframe.columns = [
        normalize_header_name(column)
        for column in dataframe.columns
    ]

    if not {
        "Expense_ID",
        "Expected_Status",
    }.issubset(
        dataframe.columns
    ):
        return {}

    expected_statuses: dict[str, str] = {}

    for _, row in dataframe.iterrows():
        expense_id = str(
            row.get(
                "Expense_ID",
                "",
            )
        ).strip()

        expected_status = str(
            row.get(
                "Expected_Status",
                "",
            )
        ).strip().upper()

        if (
            expense_id
            and expense_id.casefold()
            != "nan"
            and expected_status
            and expected_status.casefold()
            != "nan"
        ):
            expected_statuses[
                expense_id
            ] = expected_status

    return expected_statuses


def build_evaluation_dataframe(
    worksheet_result,
    expected_statuses: dict[str, str],
) -> pd.DataFrame:
    """
    Compare expected and actual statuses inside the UI.
    """

    expected_dataframe = pd.DataFrame(
        [
            {
                "Expense_ID": expense_id,
                "Expected_Status": status,
            }
            for expense_id, status
            in expected_statuses.items()
        ]
    )

    actual_dataframe = pd.DataFrame(
        [
            {
                "Expense_ID": (
                    item.claim.expense_id
                ),
                "Actual_Status": (
                    item.final_status
                ),
                "Actual_Auto_Payable": (
                    item.auto_payable
                ),
                "Result_Source": (
                    item.result_source
                ),
            }
            for item in worksheet_result.results
        ]
    )

    if expected_dataframe.empty:
        return pd.DataFrame()

    comparison = expected_dataframe.merge(
        actual_dataframe,
        on="Expense_ID",
        how="outer",
    )

    comparison["Status_Correct"] = (
        comparison["Expected_Status"]
        == comparison["Actual_Status"]
    )

    comparison[
        "Expected_Auto_Payable"
    ] = (
        comparison["Expected_Status"]
        == APPROVAL_STATUS
    )

    actual_payable = (
        comparison[
            "Actual_Auto_Payable"
        ]
        .fillna(False)
        .astype(bool)
    )

    comparison["False_Approval"] = (
        actual_payable
        & ~comparison[
            "Expected_Auto_Payable"
        ]
    )

    comparison["Missed_Approval"] = (
        comparison[
            "Expected_Auto_Payable"
        ]
        & ~actual_payable
    )

    return comparison


# ============================================================
# VISUAL HELPERS
# ============================================================

def humanize_status(
    status: str,
) -> str:
    """
    Convert a status constant into readable text.
    """

    return STATUS_LABELS.get(
        status,
        status.replace(
            "_",
            " ",
        ).title(),
    )


def get_status_group(
    status: str,
) -> str:
    """
    Return the CSS group for a final status.
    """

    return STATUS_GROUPS.get(
        status,
        "default",
    )


def render_status_badge(
    status: str,
) -> None:
    """
    Render one colored final-status badge.
    """

    safe_label = html.escape(
        humanize_status(status)
    )

    group = get_status_group(
        status
    )

    st.markdown(
        (
            f'<span class="status-badge '
            f'status-{group}">'
            f"{safe_label}"
            f"</span>"
        ),
        unsafe_allow_html=True,
    )


def display_summary_metrics(
    worksheet_result,
    result_rows: list[dict[str, Any]],
) -> None:
    """
    Display business and system performance metrics.
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
        item.result_source
        == "local_validation"
        for item in worksheet_result.results
    )

    payable_amount = sum(
        float(
            row.get(
                "Excel_Amount",
                0,
            )
            or 0
        )
        for row in result_rows
        if row.get(
            "Auto_Payable"
        ) is True
    )

    total_claims = (
        worksheet_result.total_claims
    )

    automated_count = (
        openai_count
        + cache_count
    )

    automation_rate = (
        automated_count
        / total_claims
        * 100
        if total_claims
        else 0
    )

    first_row = st.columns(4)

    first_row[0].metric(
        "Total Claims",
        total_claims,
    )

    first_row[1].metric(
        "Auto Approved",
        worksheet_result.approved_count,
    )

    first_row[2].metric(
        "Exceptions",
        worksheet_result.exception_count,
    )

    first_row[3].metric(
        "Payable Amount",
        f"₹{payable_amount:,.2f}",
    )

    second_row = st.columns(4)

    second_row[0].metric(
        "OpenAI Analyses",
        openai_count,
    )

    second_row[1].metric(
        "Cache Hits",
        cache_count,
    )

    second_row[2].metric(
        "Local Validations",
        local_count,
    )

    processing_seconds = (
        st.session_state.processing_seconds
    )

    second_row[3].metric(
        "End-to-End Time",
        (
            f"{processing_seconds:.2f} sec"
            if processing_seconds is not None
            else "—"
        ),
    )

    st.caption(
        "Agent/cache processing rate: "
        f"{automation_rate:.1f}% · "
        "Local failures and duplicates are blocked "
        "before an OpenAI request."
    )


def display_distribution_charts(
    results_dataframe: pd.DataFrame,
) -> None:
    """
    Display status and processing-source distributions.
    """

    left_column, right_column = st.columns(2)

    with left_column:
        st.markdown(
            "**Final-status distribution**"
        )

        status_counts = (
            results_dataframe[
                "Final_Status"
            ]
            .value_counts()
            .rename_axis(
                "Final Status"
            )
            .reset_index(
                name="Claims"
            )
        )

        st.bar_chart(
            status_counts,
            x="Final Status",
            y="Claims",
        )

    with right_column:
        st.markdown(
            "**Processing-source distribution**"
        )

        source_counts = (
            results_dataframe[
                "Result_Source"
            ]
            .value_counts()
            .rename_axis(
                "Result Source"
            )
            .reset_index(
                name="Claims"
            )
        )

        st.bar_chart(
            source_counts,
            x="Result Source",
            y="Claims",
        )


def filter_results_dataframe(
    results_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply status, source, payable and text-search filters.
    """

    filter_columns = st.columns(
        [2, 2, 2, 3]
    )

    status_options = sorted(
        results_dataframe[
            "Final_Status"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    source_options = sorted(
        results_dataframe[
            "Result_Source"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    selected_statuses = (
        filter_columns[0].multiselect(
            "Final Status",
            options=status_options,
            default=status_options,
        )
    )

    selected_sources = (
        filter_columns[1].multiselect(
            "Result Source",
            options=source_options,
            default=source_options,
        )
    )

    payable_filter = (
        filter_columns[2].selectbox(
            "Payment Decision",
            options=[
                "All claims",
                "Approved only",
                "Exceptions only",
            ],
        )
    )

    search_text = (
        filter_columns[3]
        .text_input(
            "Search",
            placeholder=(
                "Expense ID, employee, vendor, PDF..."
            ),
        )
        .strip()
    )

    filtered = (
        results_dataframe.copy()
    )

    filtered = filtered[
        filtered[
            "Final_Status"
        ].isin(
            selected_statuses
        )
    ]

    filtered = filtered[
        filtered[
            "Result_Source"
        ].isin(
            selected_sources
        )
    ]

    if payable_filter == "Approved only":
        filtered = filtered[
            filtered[
                "Auto_Payable"
            ]
            == True
        ]

    elif (
        payable_filter
        == "Exceptions only"
    ):
        filtered = filtered[
            filtered[
                "Auto_Payable"
            ]
            == False
        ]

    if search_text:
        searchable_columns = [
            column
            for column in [
                "Expense_ID",
                "Employee_ID",
                "Employee_Name",
                "Excel_Vendor",
                "Monthly_PDF_Name",
                "Final_Status",
                "Message",
            ]
            if column
            in filtered.columns
        ]

        searchable_text = (
            filtered[
                searchable_columns
            ]
            .fillna("")
            .astype(str)
            .agg(
                " ".join,
                axis=1,
            )
        )

        filtered = filtered[
            searchable_text.str.contains(
                search_text,
                case=False,
                regex=False,
            )
        ]

    return filtered


# ============================================================
# CLAIM EVIDENCE VIEW
# ============================================================

def find_claim_result(
    worksheet_result,
    expense_id: str,
):
    """
    Find one worksheet result by Expense_ID.
    """

    for item in worksheet_result.results:
        if (
            item.claim.expense_id
            == expense_id
        ):
            return item

    return None


def display_single_claim(
    item,
) -> None:
    """
    Display the complete audit trail for one claim.
    """

    render_status_badge(
        item.final_status
    )

    if item.auto_payable:
        st.markdown(
            """
            <div class="decision-approved">
                <strong>Payment decision:</strong>
                Approved for accounts processing.
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            """
            <div class="decision-blocked">
                <strong>Payment decision:</strong>
                Not auto-payable. Review the exception reason.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    claim = item.claim

    claim_columns = st.columns(4)

    claim_columns[0].metric(
        "Claimed Amount",
        f"₹{float(claim.claimed_amount):,.2f}",
    )

    claim_columns[1].metric(
        "Claim Date",
        claim.expense_date.isoformat(),
    )

    claim_columns[2].metric(
        "PDF Page",
        claim.receipt_page_no,
    )

    claim_columns[3].metric(
        "Result Source",
        item.result_source,
    )

    st.markdown("**Claim information**")

    claim_information = pd.DataFrame(
        [
            {
                "Field": "Expense ID",
                "Value": claim.expense_id,
            },
            {
                "Field": "Employee",
                "Value": claim.employee_name,
            },
            {
                "Field": "Category",
                "Value": claim.expense_category,
            },
            {
                "Field": "Description",
                "Value": claim.description,
            },
            {
                "Field": "Vendor",
                "Value": claim.vendor,
            },
            {
                "Field": "Payment Mode",
                "Value": claim.payment_mode,
            },
            {
                "Field": "Transaction ID",
                "Value": (
                    claim.transaction_id
                    or ""
                ),
            },
            {
                "Field": "Invoice Number",
                "Value": (
                    claim.invoice_no
                    or ""
                ),
            },
            {
                "Field": "Monthly PDF",
                "Value": (
                    claim.monthly_pdf_name
                ),
            },
        ]
    )

    st.dataframe(
        claim_information,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Final message**")

    st.info(
        item.message
    )

    workflow_result = (
        item.workflow_result
    )

    if workflow_result is None:
        st.warning(
            "This claim was blocked during local validation. "
            "No OCR or OpenAI analysis was required."
        )
        return

    evidence = (
        workflow_result.evidence
    )

    processing_result = (
        workflow_result.processing_result
    )

    evidence_tab, extracted_tab, comparison_tab, safety_tab = (
        st.tabs(
            [
                "Receipt Evidence",
                "Extracted Fields",
                "Agent Comparison",
                "Final Safety Gate",
            ]
        )
    )

    with evidence_tab:
        st.write(
            f"**Evidence status:** "
            f"{evidence.status}"
        )

        st.write(
            f"**Evidence message:** "
            f"{evidence.message}"
        )

        left_column, right_column = (
            st.columns(
                [1, 1]
            )
        )

        with left_column:
            if (
                evidence.image_path
                and Path(
                    evidence.image_path
                ).exists()
            ):
                st.image(
                    evidence.image_path,
                    caption=(
                        f"{evidence.pdf_file_name} — "
                        f"page {evidence.page_number}"
                    ),
                    use_container_width=True,
                )

            else:
                st.info(
                    "No rendered page image is available."
                )

        with right_column:
            text_source = st.radio(
                "Text evidence",
                options=[
                    "Combined Evidence",
                    "Direct PDF Text",
                    "Local OCR Text",
                ],
                horizontal=True,
                key=(
                    "text_source_"
                    + claim.expense_id
                ),
            )

            if (
                text_source
                == "Direct PDF Text"
            ):
                evidence_text = (
                    evidence.direct_pdf_text
                )

            elif (
                text_source
                == "Local OCR Text"
            ):
                evidence_text = (
                    evidence.ocr_text
                )

            else:
                evidence_text = (
                    evidence.combined_evidence_text
                )

            if evidence_text:
                st.code(
                    evidence_text,
                    language=None,
                )

            else:
                st.info(
                    "No text is available for this evidence source."
                )

    if processing_result is None:
        with extracted_tab:
            st.info(
                "No agent extraction was performed."
            )

        with comparison_tab:
            st.info(
                "No agent comparison was performed."
            )

        with safety_tab:
            st.info(
                "The claim was blocked by local validation."
            )

        return

    analysis = (
        processing_result.analysis
    )

    final_decision = (
        processing_result.final_decision
    )

    with extracted_tab:
        receipt_dataframe = pd.DataFrame(
            [
                {
                    "Field": key,
                    "Extracted Value": value,
                }
                for key, value
                in analysis.receipt.model_dump(
                    mode="json"
                ).items()
            ]
        )

        st.dataframe(
            receipt_dataframe,
            use_container_width=True,
            hide_index=True,
        )

    with comparison_tab:
        comparison_rows = [
            {
                "Check": "Amount",
                "Result": analysis.amount_match,
            },
            {
                "Check": "Date",
                "Result": analysis.date_match,
            },
            {
                "Check": "Vendor",
                "Result": analysis.vendor_match,
            },
            {
                "Check": "Description",
                "Result": analysis.description_supported,
            },
            {
                "Check": "Payment Mode",
                "Result": analysis.payment_mode_match,
            },
            {
                "Check": "Transaction ID",
                "Result": analysis.transaction_id_match,
            },
            {
                "Check": "Invoice Number",
                "Result": analysis.invoice_no_match,
            },
        ]

        st.dataframe(
            pd.DataFrame(
                comparison_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.write(
            "**Agent recommended status:** "
            f"{analysis.recommended_status}"
        )

        st.write(
            "**Analysis confidence:** "
            f"{analysis.analysis_confidence}"
        )

        st.write(
            "**Agent reasons**"
        )

        for reason in analysis.reasons:
            st.write(
                f"- {reason}"
            )

        if analysis.ambiguity_notes:
            st.warning(
                analysis.ambiguity_notes
            )

    with safety_tab:
        safety_dataframe = pd.DataFrame(
            [
                {
                    "Safety Check": key,
                    "Passed": value,
                }
                for key, value
                in final_decision.safety_checks.items()
            ]
        )

        st.dataframe(
            safety_dataframe,
            use_container_width=True,
            hide_index=True,
        )

        st.write(
            "**Final decision reasons**"
        )

        for reason in final_decision.reasons:
            st.write(
                f"- {reason}"
            )


# ============================================================
# MAIN APPLICATION
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title=(
            "AI Reimbursement Verification"
        ),
        page_icon="🧾",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_application_styles()
    initialize_session()

    st.markdown(
        """
        <div class="main-header">
            <h1>AI Reimbursement Verification Agent</h1>
            <p>
                Automated, explainable and audit-ready
                employee expense validation
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="workflow-strip">
            <strong>Workflow:</strong>
            Excel validation → Exact PDF-page mapping →
            Local OCR → Structured agent analysis →
            Deterministic safety gate → Accounts-ready report
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:
        st.subheader(
            "Processing Controls"
        )

        st.info(
            "Uncached valid claims may use one OpenAI "
            "analysis request each. Duplicate pages, missing "
            "PDFs and missing pages are blocked locally."
        )

        if st.button(
            "Clear Processed Results",
            use_container_width=True,
        ):
            clear_processed_results()
            st.rerun()

        st.divider()

        st.subheader(
            "Safety Architecture"
        )

        st.write(
            "The agent recommends. "
            "The deterministic safety gate decides."
        )

        st.write(
            "- Exact amount validation\n"
            "- Exact date validation\n"
            "- Exact transaction-ID validation\n"
            "- Duplicate-page prevention\n"
            "- Confidence threshold enforcement\n"
            "- No automatic payment on ambiguity"
        )

        st.divider()

        st.caption(
            "Use synthetic data for demos. "
            "Do not commit employee receipts or API keys."
        )

    # --------------------------------------------------------
    # UPLOAD SECTION
    # --------------------------------------------------------

    st.subheader(
        "1. Upload reimbursement files"
    )

    upload_left, upload_right = (
        st.columns(2)
    )

    with upload_left:
        excel_upload = st.file_uploader(
            "Employee reimbursement workbook",
            type=["xlsx"],
            accept_multiple_files=False,
            help=(
                "The workbook may contain multiple "
                "monthly worksheets."
            ),
        )

    with upload_right:
        pdf_uploads = st.file_uploader(
            "Monthly receipt PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            help=(
                "Upload every monthly PDF referenced "
                "by the selected worksheet."
            ),
        )

    if excel_upload is None:
        st.info(
            "Upload an Excel workbook to begin."
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
        destination_directory=(
            excel_directory
        ),
    )

    synchronize_uploaded_pdfs(
        pdf_uploads=pdf_uploads,
        pdf_directory=pdf_directory,
    )

    # --------------------------------------------------------
    # WORKSHEET SELECTION
    # --------------------------------------------------------

    try:
        worksheet_names = (
            list_worksheet_names(
                excel_path
            )
        )

    except Exception as error:
        st.error(
            "The uploaded workbook could not be read."
        )

        st.exception(error)
        return

    if not worksheet_names:
        st.error(
            "No readable worksheets were found."
        )
        return

    st.subheader(
        "2. Select and validate a monthly worksheet"
    )

    worksheet_name = st.selectbox(
        "Monthly worksheet",
        options=worksheet_names,
    )

    try:
        claims, excel_errors = (
            read_claims_from_worksheet(
                file_path=excel_path,
                worksheet_name=worksheet_name,
            )
        )

    except Exception as error:
        st.error(
            "The selected worksheet could not be validated."
        )

        st.exception(error)
        return

    expected_statuses = (
        read_expected_statuses(
            excel_path=excel_path,
            worksheet_name=worksheet_name,
        )
    )

    current_input_signature = (
        build_input_signature(
            excel_upload=excel_upload,
            pdf_uploads=pdf_uploads,
            worksheet_name=worksheet_name,
        )
    )

    if (
        st.session_state.processed_input_signature
        is not None
        and
        st.session_state.processed_input_signature
        != current_input_signature
    ):
        clear_processed_results()

    validation_columns = st.columns(4)

    validation_columns[0].metric(
        "Valid Claims",
        len(claims),
    )

    validation_columns[1].metric(
        "Excel Errors",
        len(excel_errors),
    )

    validation_columns[2].metric(
        "Uploaded PDFs",
        len(pdf_uploads),
    )

    validation_columns[3].metric(
        "Evaluation Mode",
        (
            "Active"
            if expected_statuses
            else "Off"
        ),
    )

    readiness_dataframe = (
        build_pdf_readiness_dataframe(
            claims=claims,
            pdf_directory=pdf_directory,
        )
    )

    missing_pdf_names: list[str] = []

    if not readiness_dataframe.empty:
        missing_pdf_names = (
            readiness_dataframe[
                readiness_dataframe[
                    "Available"
                ]
                == False
            ][
                "Referenced PDF"
            ]
            .astype(str)
            .tolist()
        )

    preview_tab, readiness_tab, errors_tab = (
        st.tabs(
            [
                "Validated Claims",
                "PDF Readiness",
                "Excel Errors",
            ]
        )
    )

    with preview_tab:
        claims_dataframe = (
            claims_to_dataframe(
                claims
            )
        )

        if claims_dataframe.empty:
            st.warning(
                "No valid claims were found."
            )

        else:
            st.dataframe(
                claims_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    with readiness_tab:
        if readiness_dataframe.empty:
            st.info(
                "No PDF references were found."
            )

        else:
            st.dataframe(
                readiness_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            if missing_pdf_names:
                st.warning(
                    "Missing referenced PDFs:\n\n"
                    + "\n".join(
                        f"- {file_name}"
                        for file_name
                        in missing_pdf_names
                    )
                )

    with errors_tab:
        if excel_errors:
            st.dataframe(
                pd.DataFrame(
                    excel_errors
                ),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.success(
                "No Excel validation errors were found."
            )

    # --------------------------------------------------------
    # RUN PROCESSING
    # --------------------------------------------------------

    st.subheader(
        "3. Run verification"
    )

    st.caption(
        "Claims can still be processed without every PDF. "
        "Missing files and pages will be reported as local exceptions."
    )

    run_clicked = st.button(
        "Run Reimbursement Verification",
        type="primary",
        disabled=not claims,
        use_container_width=True,
    )

    if run_clicked:
        clear_processed_results()

        progress_bar = st.progress(
            0
        )

        progress_message = st.empty()

        try:
            processing_start_time = (
                time.perf_counter()
            )

            progress_message.write(
                "Validating claim mappings..."
            )

            progress_bar.progress(
                10
            )

            progress_message.write(
                "Preparing exact PDF-page evidence..."
            )

            progress_bar.progress(
                25
            )

            worksheet_result = (
                process_monthly_worksheet(
                    excel_path=excel_path,
                    worksheet_name=worksheet_name,
                    pdf_directory=pdf_directory,
                )
            )

            progress_message.write(
                "Applying final safety decisions..."
            )

            progress_bar.progress(
                80
            )

            safe_worksheet_name = (
                worksheet_name
                .replace(
                    "/",
                    "-",
                )
                .replace(
                    "\\",
                    "-",
                )
            )

            report_name = (
                f"{safe_worksheet_name}"
                "_reimbursement_report.xlsx"
            )

            report_path = (
                REPORT_ROOT
                / st.session_state.session_id
                / (
                    current_input_signature[
                        :12
                    ]
                    + "_"
                    + report_name
                )
            )

            progress_message.write(
                "Generating the audit-ready Excel report..."
            )

            generated_report = (
                generate_worksheet_report(
                    worksheet_result=(
                        worksheet_result
                    ),
                    output_path=(
                        report_path
                    ),
                )
            )

            st.session_state.processing_seconds = (
                round(
                    time.perf_counter()
                    - processing_start_time,
                    3,
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

            st.session_state.processed_input_signature = (
                current_input_signature
            )

            progress_bar.progress(
                100
            )

            progress_message.success(
                "Verification and report generation completed."
            )

        except MaxTurnsExceeded:
            st.error(
                "The analysis agent exceeded its configured "
                "one-turn execution limit."
            )

        except ModelRefusalError:
            st.error(
                "The model refused one reimbursement "
                "analysis request."
            )

        except ModelBehaviorError as error:
            st.error(
                "The model returned invalid structured output."
            )

            st.code(
                str(error)
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
                "The reimbursement workflow failed."
            )

            st.exception(error)

    worksheet_result = (
        st.session_state.worksheet_result
    )

    if worksheet_result is None:
        return

    # --------------------------------------------------------
    # RESULT DASHBOARD
    # --------------------------------------------------------

    result_rows = build_result_rows(
        worksheet_result
    )

    results_dataframe = pd.DataFrame(
        result_rows
    )

    st.success(
        "Reimbursement verification completed successfully."
    )

    st.subheader(
        "4. Verification dashboard"
    )

    dashboard_tabs = st.tabs(
        [
            "Overview",
            "All Results",
            "Approvals",
            "Exceptions",
            "Claim Evidence",
            "Evaluation",
            "Reports",
        ]
    )

    # --------------------------------------------------------
    # OVERVIEW
    # --------------------------------------------------------

    with dashboard_tabs[0]:
        display_summary_metrics(
            worksheet_result=(
                worksheet_result
            ),
            result_rows=result_rows,
        )

        st.divider()

        if not results_dataframe.empty:
            display_distribution_charts(
                results_dataframe
            )

        st.divider()

        st.markdown(
            """
            **Decision architecture**

            The OpenAI agent extracts receipt fields and performs
            semantic comparison. Exact arithmetic, identifiers,
            duplicate-page protection and the final payment decision
            remain controlled by deterministic Python validation.
            """
        )

    # --------------------------------------------------------
    # ALL RESULTS
    # --------------------------------------------------------

    with dashboard_tabs[1]:
        if results_dataframe.empty:
            st.info(
                "No claim results are available."
            )

        else:
            filtered_results = (
                filter_results_dataframe(
                    results_dataframe
                )
            )

            st.caption(
                f"Displaying "
                f"{len(filtered_results)} "
                f"of "
                f"{len(results_dataframe)} "
                f"claims."
            )

            preferred_columns = [
                column
                for column in [
                    "Expense_ID",
                    "Employee_Name",
                    "Excel_Date",
                    "Expense_Category",
                    "Excel_Amount",
                    "Excel_Vendor",
                    "Monthly_PDF_Name",
                    "Receipt_Page_No",
                    "Result_Source",
                    "Final_Status",
                    "Auto_Payable",
                    "Message",
                ]
                if column
                in filtered_results.columns
            ]

            st.dataframe(
                filtered_results[
                    preferred_columns
                ],
                use_container_width=True,
                hide_index=True,
            )

            filtered_csv = (
                filtered_results.to_csv(
                    index=False
                ).encode(
                    "utf-8"
                )
            )

            st.download_button(
                "Download Filtered Results CSV",
                data=filtered_csv,
                file_name=(
                    f"{worksheet_name}"
                    "_filtered_results.csv"
                ),
                mime="text/csv",
            )

    # --------------------------------------------------------
    # APPROVALS
    # --------------------------------------------------------

    with dashboard_tabs[2]:
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

        if approved_dataframe.empty:
            st.info(
                "No claims were approved for accounts."
            )

        else:
            approved_amount = (
                approved_dataframe[
                    "Excel_Amount"
                ]
                .fillna(0)
                .astype(float)
                .sum()
            )

            approved_columns = st.columns(2)

            approved_columns[0].metric(
                "Approved Claims",
                len(
                    approved_dataframe
                ),
            )

            approved_columns[1].metric(
                "Approved Amount",
                f"₹{approved_amount:,.2f}",
            )

            st.dataframe(
                approved_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------------
    # EXCEPTIONS
    # --------------------------------------------------------

    with dashboard_tabs[3]:
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

        if exception_dataframe.empty:
            st.success(
                "No exceptions were found."
            )

        else:
            exception_statuses = (
                exception_dataframe[
                    "Final_Status"
                ]
                .value_counts()
                .rename_axis(
                    "Exception Status"
                )
                .reset_index(
                    name="Claims"
                )
            )

            st.bar_chart(
                exception_statuses,
                x="Exception Status",
                y="Claims",
            )

            st.dataframe(
                exception_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------------
    # CLAIM EVIDENCE
    # --------------------------------------------------------

    with dashboard_tabs[4]:
        expense_ids = [
            item.claim.expense_id
            for item in worksheet_result.results
        ]

        selected_expense_id = (
            st.selectbox(
                "Select a claim",
                options=expense_ids,
            )
        )

        selected_item = (
            find_claim_result(
                worksheet_result=(
                    worksheet_result
                ),
                expense_id=(
                    selected_expense_id
                ),
            )
        )

        if selected_item is not None:
            display_single_claim(
                selected_item
            )

    # --------------------------------------------------------
    # EVALUATION
    # --------------------------------------------------------

    with dashboard_tabs[5]:
        if not expected_statuses:
            st.info(
                "Evaluation mode is not active because this "
                "workbook does not contain an Expected_Status column."
            )

        else:
            evaluation_dataframe = (
                build_evaluation_dataframe(
                    worksheet_result=(
                        worksheet_result
                    ),
                    expected_statuses=(
                        expected_statuses
                    ),
                )
            )

            total_cases = len(
                evaluation_dataframe
            )

            correct_cases = int(
                evaluation_dataframe[
                    "Status_Correct"
                ].sum()
            )

            false_approvals = int(
                evaluation_dataframe[
                    "False_Approval"
                ].sum()
            )

            missed_approvals = int(
                evaluation_dataframe[
                    "Missed_Approval"
                ].sum()
            )

            accuracy = (
                correct_cases
                / total_cases
                * 100
                if total_cases
                else 0
            )

            evaluation_columns = (
                st.columns(4)
            )

            evaluation_columns[0].metric(
                "Evaluation Cases",
                total_cases,
            )

            evaluation_columns[1].metric(
                "Status Accuracy",
                f"{accuracy:.2f}%",
            )

            evaluation_columns[2].metric(
                "False Approvals",
                false_approvals,
            )

            evaluation_columns[3].metric(
                "Missed Approvals",
                missed_approvals,
            )

            if (
                false_approvals == 0
                and missed_approvals == 0
                and correct_cases
                == total_cases
            ):
                st.success(
                    "All expected statuses matched. "
                    "No unsafe approval was detected."
                )

            else:
                st.warning(
                    "One or more evaluation cases did not "
                    "match the expected result."
                )

            st.dataframe(
                evaluation_dataframe,
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------------
    # REPORT DOWNLOADS
    # --------------------------------------------------------

    with dashboard_tabs[6]:
        st.markdown(
            "**Generated reimbursement report**"
        )

        st.write(
            "The report contains:"
        )

        st.write(
            "- Summary\n"
            "- Approved_For_Accounts\n"
            "- Exception_Report\n"
            "- All_Results\n"
            "- AI_Page_Evidence\n"
            "- Excel_Errors"
        )

        if (
            st.session_state.report_bytes
            is not None
            and
            st.session_state.report_name
            is not None
        ):
            st.download_button(
                label=(
                    "Download Final Excel Report"
                ),
                data=(
                    st.session_state.report_bytes
                ),
                file_name=(
                    st.session_state.report_name
                ),
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                type="primary",
                use_container_width=True,
            )

        else:
            st.warning(
                "The report file is not available."
            )


if __name__ == "__main__":
    main()