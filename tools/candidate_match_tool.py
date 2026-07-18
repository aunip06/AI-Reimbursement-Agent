from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from models.claim import Claim
from models.receipt_candidate_evidence import (
    CandidateReceiptEvidence,
)


COMMON_WORDS = {
    "and",
    "for",
    "from",
    "the",
    "with",
    "payment",
    "receipt",
    "services",
    "service",
    "expense",
    "private",
    "limited",
    "ltd",
    "india",
}


def normalize_identifier(
    value: str | None,
) -> str:
    """
    Normalize transaction and invoice identifiers.
    """

    if not value:
        return ""

    return re.sub(
        r"[^a-z0-9]",
        "",
        value.casefold(),
    )


def normalize_search_text(
    text: str,
) -> str:
    """
    Normalize evidence text while retaining word boundaries.
    """

    return re.sub(
        r"\s+",
        " ",
        text.casefold(),
    ).strip()


def tokenize(
    value: str | None,
) -> set[str]:
    """
    Create meaningful comparison tokens.
    """

    if not value:
        return set()

    tokens = set(
        re.findall(
            r"[a-z0-9]+",
            value.casefold(),
        )
    )

    return {
        token
        for token in tokens
        if (
            len(token) >= 3
            and token not in COMMON_WORDS
        )
    }


def token_overlap_ratio(
    expected_value: str | None,
    evidence_text: str,
) -> float:
    """
    Calculate how many expected tokens occur in evidence.
    """

    expected_tokens = tokenize(
        expected_value
    )

    if not expected_tokens:
        return 0.0

    evidence_tokens = tokenize(
        evidence_text
    )

    matched_tokens = (
        expected_tokens
        & evidence_tokens
    )

    return (
        len(matched_tokens)
        / len(expected_tokens)
    )


def build_amount_variants(
    amount: Decimal,
) -> set[str]:
    """
    Build common textual forms of a claimed amount.
    """

    normalized = amount.quantize(
        Decimal("0.01")
    )

    plain_two_decimals = (
        f"{normalized:.2f}"
    )

    plain_without_decimals = (
        str(
            int(normalized)
        )
        if normalized
        == normalized.to_integral_value()
        else ""
    )

    comma_two_decimals = (
        f"{normalized:,.2f}"
    )

    comma_without_decimals = (
        f"{int(normalized):,}"
        if plain_without_decimals
        else ""
    )

    variants = {
        plain_two_decimals,
        plain_without_decimals,
        comma_two_decimals,
        comma_without_decimals,
    }

    return {
        value
        for value in variants
        if value
    }


def amount_found_in_text(
    amount: Decimal,
    evidence_text: str,
) -> bool:
    """
    Check whether a claimed amount occurs in candidate text.
    """

    compact_text = (
        normalize_search_text(
            evidence_text
        )
    )

    for amount_variant in build_amount_variants(
        amount
    ):
        pattern = (
            r"(?<!\d)"
            + re.escape(
                amount_variant.casefold()
            )
            + r"(?!\d)"
        )

        if re.search(
            pattern,
            compact_text,
        ):
            return True

    return False


def build_date_variants(
    expense_date: date,
) -> set[str]:
    """
    Build common receipt-date representations.
    """

    month_short = (
        expense_date.strftime("%b")
    )

    month_long = (
        expense_date.strftime("%B")
    )

    return {
        expense_date.isoformat(),
        expense_date.strftime(
            "%d-%m-%Y"
        ),
        expense_date.strftime(
            "%d/%m/%Y"
        ),
        expense_date.strftime(
            "%d.%m.%Y"
        ),
        expense_date.strftime(
            "%d %b %Y"
        ),
        expense_date.strftime(
            "%d %B %Y"
        ),
        (
            f"{expense_date.day} "
            f"{month_short} "
            f"{expense_date.year}"
        ),
        (
            f"{expense_date.day} "
            f"{month_long} "
            f"{expense_date.year}"
        ),
    }


def date_found_in_text(
    expense_date: date,
    evidence_text: str,
) -> bool:
    """
    Check whether the claim date occurs in candidate text.
    """

    normalized_text = (
        normalize_search_text(
            evidence_text
        )
    )

    return any(
        date_variant.casefold()
        in normalized_text
        for date_variant
        in build_date_variants(
            expense_date
        )
    )


def identifier_found_in_text(
    identifier: str | None,
    evidence_text: str,
) -> bool:
    """
    Search for an exact normalized identifier.
    """

    normalized_identifier = (
        normalize_identifier(
            identifier
        )
    )

    if not normalized_identifier:
        return False

    normalized_evidence = (
        normalize_identifier(
            evidence_text
        )
    )

    return (
        normalized_identifier
        in normalized_evidence
    )


def score_candidate_locally(
    claim: Claim,
    candidate_evidence: CandidateReceiptEvidence,
) -> dict:
    """
    Rank one candidate using deterministic evidence only.

    This stage never approves a claim.
    """

    evidence_text = (
        candidate_evidence
        .combined_evidence_text
    )

    reasons: list[str] = []

    score = 0.0

    transaction_id_found = (
        identifier_found_in_text(
            claim.transaction_id,
            evidence_text,
        )
    )

    invoice_no_found = (
        identifier_found_in_text(
            claim.invoice_no,
            evidence_text,
        )
    )

    amount_found = (
        amount_found_in_text(
            claim.claimed_amount,
            evidence_text,
        )
    )

    date_found = (
        date_found_in_text(
            claim.expense_date,
            evidence_text,
        )
    )

    vendor_overlap = (
        token_overlap_ratio(
            claim.vendor,
            evidence_text,
        )
    )

    description_overlap = (
        token_overlap_ratio(
            claim.description,
            evidence_text,
        )
    )

    if transaction_id_found:
        score += 45.0

        reasons.append(
            "Exact claimed transaction ID "
            "appears in this candidate."
        )

    if invoice_no_found:
        score += 40.0

        reasons.append(
            "Exact claimed invoice number "
            "appears in this candidate."
        )

    if amount_found:
        score += 25.0

        reasons.append(
            "Claimed amount appears in this candidate."
        )

    if date_found:
        score += 15.0

        reasons.append(
            "Claim date appears in this candidate."
        )

    if vendor_overlap > 0:
        vendor_score = min(
            10.0,
            vendor_overlap * 10.0,
        )

        score += vendor_score

        reasons.append(
            "Vendor token overlap: "
            f"{vendor_overlap:.2f}."
        )

    if description_overlap > 0:
        description_score = min(
            5.0,
            description_overlap * 5.0,
        )

        score += description_score

        reasons.append(
            "Description token overlap: "
            f"{description_overlap:.2f}."
        )

    score += min(
        5.0,
        candidate_evidence.ocr_score
        / 20.0,
    )

    if not reasons:
        reasons.append(
            "No strong deterministic claim evidence "
            "was found in this candidate."
        )

    return {
        "candidate_no": (
            candidate_evidence
            .candidate
            .candidate_no
        ),
        "local_score": round(
            min(
                100.0,
                score,
            ),
            3,
        ),
        "local_reasons": reasons,
        "exact_transaction_id_found": (
            transaction_id_found
        ),
        "exact_invoice_no_found": (
            invoice_no_found
        ),
        "amount_text_found": (
            amount_found
        ),
        "date_text_found": (
            date_found
        ),
    }


def calculate_semantic_score(
    analysis,
) -> float:
    """
    Rank agent comparison quality for candidate selection.

    This score does not replace the final payment safety gate.
    """

    score = 0.0

    if analysis.receipt.bill_found:
        score += 10.0

    if analysis.amount_match is True:
        score += 30.0

    if analysis.date_match is True:
        score += 20.0

    if analysis.vendor_match is True:
        score += 15.0

    if (
        analysis.description_supported
        is True
    ):
        score += 10.0

    if (
        analysis.payment_mode_match
        is True
    ):
        score += 10.0

    if (
        analysis.transaction_id_match
        is True
    ):
        score += 45.0

    if (
        analysis.invoice_no_match
        is True
    ):
        score += 40.0

    if (
        analysis.analysis_confidence
        == "high"
    ):
        score += 15.0

    elif (
        analysis.analysis_confidence
        == "medium"
    ):
        score += 5.0

    return round(
        min(
            200.0,
            score,
        ),
        3,
    )


def is_strict_candidate_match(
    claim: Claim,
    analysis,
) -> bool:
    """
    Determine whether one candidate can be uniquely
    associated with the claim.

    This selects evidence only. It does not approve payment.
    """

    if not analysis.receipt.bill_found:
        return False

    if analysis.amount_match is not True:
        return False

    if analysis.date_match is not True:
        return False

    if analysis.vendor_match is False:
        return False

    if (
        analysis.payment_mode_match
        is False
    ):
        return False

    if claim.transaction_id:
        if (
            analysis.transaction_id_match
            is not True
        ):
            return False

    if claim.invoice_no:
        if (
            analysis.invoice_no_match
            is not True
        ):
            return False

    if (
        not claim.transaction_id
        and not claim.invoice_no
    ):
        if (
            analysis.vendor_match
            is not True
        ):
            return False

        if (
            analysis.analysis_confidence
            != "high"
        ):
            return False

    return True