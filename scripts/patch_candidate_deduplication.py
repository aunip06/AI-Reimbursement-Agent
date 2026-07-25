from pathlib import Path


DETECTOR_PATH = Path(
    "tools/receipt_candidate_detector.py"
)

BACKUP_PATH = Path(
    "tools/receipt_candidate_detector.py.before_dedup_fix"
)


NEW_FUNCTION = '''def remove_duplicate_proposals(
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove duplicated, nested and mixed wrapper detections.

    Important rules:

    - Native PDF image regions receive first priority.
    - Internal UI panels inside a screenshot are removed.
    - A large region containing multiple independent receipts
      is removed so their OCR evidence cannot be mixed.
    """

    source_priority = {
        "native_pdf_image": 3,
        "visual_region": 2,
        "full_page_fallback": 1,
    }

    ordered = sorted(
        proposals,
        key=lambda proposal: (
            source_priority.get(
                proposal["source"],
                0,
            ),
            box_area(
                proposal["box"]
            ),
            proposal["confidence"],
        ),
        reverse=True,
    )

    selected: list[
        dict[str, Any]
    ] = []

    for proposal in ordered:
        proposal_box = proposal[
            "box"
        ]

        proposal_area = max(
            1,
            box_area(
                proposal_box
            ),
        )

        should_skip = False

        contained_existing: list[
            dict[str, Any]
        ] = []

        for existing in selected:
            existing_box = existing[
                "box"
            ]

            existing_area = max(
                1,
                box_area(
                    existing_box
                ),
            )

            overlap = (
                intersection_over_union(
                    proposal_box,
                    existing_box,
                )
            )

            proposal_inside_existing = (
                containment_ratio(
                    proposal_box,
                    existing_box,
                )
            )

            existing_inside_proposal = (
                containment_ratio(
                    existing_box,
                    proposal_box,
                )
            )

            # Nearly identical detections.
            if overlap >= 0.45:
                should_skip = True
                break

            # Internal panel or text group inside an already
            # accepted receipt image.
            if (
                proposal_inside_existing
                >= 0.72
            ):
                should_skip = True
                break

            # Visual contours often detect internal UI regions
            # inside a native PDF screenshot. Remove them more
            # aggressively.
            if (
                proposal["source"]
                == "visual_region"
                and existing["source"]
                == "native_pdf_image"
            ):
                if (
                    proposal_inside_existing
                    >= 0.55
                ):
                    should_skip = True
                    break

                if (
                    existing_inside_proposal
                    >= 0.72
                    and proposal_area
                    <= existing_area * 1.80
                ):
                    should_skip = True
                    break

            if (
                existing_inside_proposal
                >= 0.70
            ):
                contained_existing.append(
                    existing
                )

        if should_skip:
            continue

        # A visual wrapper containing two or more already
        # accepted receipt regions must not become another
        # candidate because its OCR would mix those receipts.
        if (
            proposal["source"]
            == "visual_region"
            and len(
                contained_existing
            )
            >= 2
        ):
            combined_intersection = sum(
                intersection_area(
                    existing["box"],
                    proposal_box,
                )
                for existing
                in contained_existing
            )

            coverage_ratio = (
                combined_intersection
                / proposal_area
            )

            if coverage_ratio >= 0.20:
                continue

        selected.append(
            proposal
        )

    final_proposals: list[
        dict[str, Any]
    ] = []

    for proposal in selected:
        proposal_box = proposal[
            "box"
        ]

        proposal_area = max(
            1,
            box_area(
                proposal_box
            ),
        )

        contained_candidates = [
            other
            for other in selected
            if other is not proposal
            and containment_ratio(
                other["box"],
                proposal_box,
            )
            >= 0.68
            and box_area(
                other["box"]
            )
            >= (
                proposal_area
                * 0.025
            )
        ]

        # Remove large wrapper regions that surround multiple
        # independent candidates.
        if (
            proposal["source"]
            == "visual_region"
            and len(
                contained_candidates
            )
            >= 2
        ):
            continue

        # Remove visual fragments that remain substantially
        # inside a native screenshot.
        visual_inside_native = any(
            proposal["source"]
            == "visual_region"
            and other["source"]
            == "native_pdf_image"
            and containment_ratio(
                proposal_box,
                other["box"],
            )
            >= 0.60
            for other in selected
            if other is not proposal
        )

        if visual_inside_native:
            continue

        final_proposals.append(
            proposal
        )

    return final_proposals
'''


def main() -> None:
    if not DETECTOR_PATH.exists():
        raise FileNotFoundError(
            f"Detector not found: {DETECTOR_PATH}"
        )

    source = DETECTOR_PATH.read_text(
        encoding="utf-8"
    )

    start_marker = (
        "def remove_duplicate_proposals("
    )

    end_marker = (
        "\ndef crop_fingerprint("
    )

    start_position = source.find(
        start_marker
    )

    if start_position == -1:
        raise RuntimeError(
            "remove_duplicate_proposals() was not found."
        )

    end_position = source.find(
        end_marker,
        start_position,
    )

    if end_position == -1:
        raise RuntimeError(
            "crop_fingerprint() marker was not found."
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
        + NEW_FUNCTION
        + source[end_position:]
    )

    DETECTOR_PATH.write_text(
        updated_source,
        encoding="utf-8",
    )

    print(
        "Candidate deduplication patch applied successfully."
    )


if __name__ == "__main__":
    main()