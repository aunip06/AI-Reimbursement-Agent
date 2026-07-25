from pathlib import Path


APP_PATH = Path("app.py")
BACKUP_PATH = Path("app_before_candidate_evidence_ui.py")


NEW_EVIDENCE_BLOCK = '''    with evidence_tab:
        candidate_count = getattr(
            evidence,
            "candidate_count",
            0,
        )

        selected_candidate_no = getattr(
            evidence,
            "selected_candidate_no",
            None,
        )

        selection_status = getattr(
            evidence,
            "candidate_selection_status",
            None,
        )

        candidate_image_paths = getattr(
            evidence,
            "candidate_image_paths",
            [],
        ) or []

        annotated_page_image_path = getattr(
            evidence,
            "annotated_page_image_path",
            None,
        )

        selected_fingerprint = getattr(
            evidence,
            "selected_candidate_fingerprint",
            None,
        )

        evidence_metrics = st.columns(4)

        evidence_metrics[0].metric(
            "Evidence Status",
            evidence.status,
        )

        evidence_metrics[1].metric(
            "Detected Candidates",
            candidate_count,
        )

        evidence_metrics[2].metric(
            "Selected Candidate",
            (
                selected_candidate_no
                if selected_candidate_no is not None
                else "None"
            ),
        )

        evidence_metrics[3].metric(
            "Selection Status",
            selection_status or "Not applicable",
        )

        st.markdown("**Evidence message**")

        st.info(
            evidence.message
        )

        if evidence.status == "EMPTY_PAGE":
            st.warning(
                "The referenced PDF page was detected as blank. "
                "No receipt analysis or payment approval was performed."
            )

        elif (
            evidence.status
            == "AMBIGUOUS_RECEIPT_SELECTION"
        ):
            st.error(
                "Multiple receipt candidates could correspond to "
                "this claim. Automatic selection and payment were blocked."
            )

        elif (
            evidence.status
            == "BILL_NOT_FOUND_ON_PAGE"
        ):
            st.warning(
                "The page was available, but no receipt candidate "
                "could be uniquely associated with this claim."
            )

        elif evidence.status == "PDF_MISSING":
            st.error(
                "The referenced monthly PDF was not uploaded."
            )

        elif evidence.status == "PAGE_MISSING":
            st.error(
                "The referenced page number does not exist in the PDF."
            )

        (
            candidate_map_tab,
            selected_receipt_tab,
            all_candidates_tab,
            text_evidence_tab,
        ) = st.tabs(
            [
                "Candidate Map",
                "Selected Receipt",
                "All Candidates",
                "Text Evidence",
            ]
        )

        with candidate_map_tab:
            if (
                annotated_page_image_path
                and Path(
                    annotated_page_image_path
                ).exists()
            ):
                st.image(
                    annotated_page_image_path,
                    caption=(
                        f"{evidence.pdf_file_name} - "
                        f"page {evidence.page_number}: "
                        f"{candidate_count} detected candidate(s)"
                    ),
                    use_container_width=True,
                )

                st.caption(
                    "Each outlined region was detected and processed "
                    "as an independent receipt candidate."
                )

            elif (
                evidence.image_path
                and Path(
                    evidence.image_path
                ).exists()
            ):
                st.image(
                    evidence.image_path,
                    caption=(
                        f"{evidence.pdf_file_name} - "
                        f"page {evidence.page_number}"
                    ),
                    use_container_width=True,
                )

                st.info(
                    "A separate candidate-map image is not available "
                    "for this evidence result."
                )

            else:
                st.info(
                    "No page or candidate-map image is available."
                )

        with selected_receipt_tab:
            if (
                selected_candidate_no is not None
                and evidence.image_path
                and Path(
                    evidence.image_path
                ).exists()
            ):
                st.success(
                    f"Candidate {selected_candidate_no} was selected "
                    "as the receipt associated with this claim."
                )

                st.image(
                    evidence.image_path,
                    caption=(
                        f"Selected Candidate "
                        f"{selected_candidate_no}"
                    ),
                    use_container_width=True,
                )

                if selected_fingerprint:
                    with st.expander(
                        "Selected receipt identity"
                    ):
                        st.code(
                            selected_fingerprint,
                            language=None,
                        )

                        st.caption(
                            "This fingerprint identifies the exact "
                            "receipt crop and prevents the same receipt "
                            "from being claimed more than once."
                        )

            elif selection_status == "AMBIGUOUS_MATCH":
                st.warning(
                    "No candidate was selected because more than one "
                    "receipt could correspond to this claim."
                )

            elif selection_status in {
                "NO_MATCH",
                "NO_CANDIDATES",
                "BLANK_PAGE",
            }:
                st.info(
                    "No receipt candidate was selected for this claim."
                )

            else:
                st.info(
                    "No selected receipt image is available."
                )

        with all_candidates_tab:
            valid_candidate_paths = [
                candidate_path
                for candidate_path in candidate_image_paths
                if (
                    candidate_path
                    and Path(
                        candidate_path
                    ).exists()
                )
            ]

            if not valid_candidate_paths:
                st.info(
                    "No independently cropped candidate images "
                    "are available."
                )

            else:
                st.write(
                    f"Detected **{len(valid_candidate_paths)}** "
                    "independent receipt candidate(s)."
                )

                candidate_columns = st.columns(2)

                for candidate_index, candidate_path in enumerate(
                    valid_candidate_paths,
                    start=1,
                ):
                    column = candidate_columns[
                        (candidate_index - 1) % 2
                    ]

                    is_selected = (
                        candidate_index
                        == selected_candidate_no
                    )

                    with column:
                        if is_selected:
                            st.success(
                                f"Candidate {candidate_index} - Selected"
                            )

                        else:
                            st.markdown(
                                f"**Candidate {candidate_index}**"
                            )

                        st.image(
                            candidate_path,
                            caption=(
                                f"Candidate {candidate_index}"
                                + (
                                    " - selected for this claim"
                                    if is_selected
                                    else ""
                                )
                            ),
                            use_container_width=True,
                        )

        with text_evidence_tab:
            if selected_candidate_no is not None:
                st.caption(
                    f"The text below belongs only to selected "
                    f"Candidate {selected_candidate_no}. "
                    "Text from other candidates was not combined."
                )

            text_source = st.radio(
                "Text evidence source",
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

'''


def main() -> None:
    if not APP_PATH.exists():
        raise FileNotFoundError(
            "app.py was not found in the current directory."
        )

    source = APP_PATH.read_text(
        encoding="utf-8"
    )

    function_marker = (
        "def display_single_claim("
    )

    function_position = source.find(
        function_marker
    )

    if function_position == -1:
        raise RuntimeError(
            "display_single_claim() was not found."
        )

    start_marker = (
        "    with evidence_tab:\n"
    )

    start_position = source.find(
        start_marker,
        function_position,
    )

    if start_position == -1:
        raise RuntimeError(
            "The Receipt Evidence block was not found."
        )

    end_marker = (
        "    if processing_result is None:\n"
    )

    end_position = source.find(
        end_marker,
        start_position,
    )

    if end_position == -1:
        raise RuntimeError(
            "The end of the Receipt Evidence block was not found."
        )

    if not BACKUP_PATH.exists():
        BACKUP_PATH.write_text(
            source,
            encoding="utf-8",
        )

        print(
            f"Backup created: {BACKUP_PATH}"
        )

    updated_source = (
        source[:start_position]
        + NEW_EVIDENCE_BLOCK
        + source[end_position:]
    )

    APP_PATH.write_text(
        updated_source,
        encoding="utf-8",
    )

    print(
        "Claim Evidence UI replaced successfully."
    )


if __name__ == "__main__":
    main()