from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable

from models.claim import Claim
from models.final_decision import (
    FinalDecision,
    FinalStatus,
)
from models.reimbursement_analysis import (
    ReimbursementAnalysis,
)


DIGITAL_PAYMENT_MODES = {
    "upi",
    "card",
    "wallet",
    "bank_transfer",
}


def amounts_equal(
    claimed_amount: Decimal,
    extracted_amount: float | None,
) -> bool:
    """
    Compare amounts exactly to two decimal places.
    """

    if extracted_amount is None:
        return False

    try:
        normalized_claimed = claimed_amount.quantize(
            Decimal("0.01")
        )

        normalized_extracted = Decimal(
            str(extracted_amount)
        ).quantize(
            Decimal("0.01")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return False

    return normalized_claimed == normalized_extracted


def dates_equal(
    claimed_date: date,
    extracted_date: str | None,
) -> bool:
    """
    Compare the claim date and extracted date exactly.
    """

    if not extracted_date:
        return False

    try:
        normalized_extracted = date.fromisoformat(
            extracted_date
        )

    except ValueError:
        return False

    return claimed_date == normalized_extracted


def normalize_identifier(
    value: str | None,
) -> str:
    """
    Normalize an identifier without changing its actual content.

    Only whitespace and letter casing are ignored.
    """

    if not value:
        return ""

    return "".join(
        str(value).split()
    ).casefold()


def identifier_matches_any(
    expected: str | None,
    candidates: Iterable[str | None],
) -> bool:
    """
    Compare one expected identifier against possible extracted IDs.
    """

    normalized_expected = normalize_identifier(
        expected
    )

    if not normalized_expected:
        return False

    return any(
        normalized_expected
        == normalize_identifier(candidate)
        for candidate in candidates
        if candidate
    )


def apply_approval_safety_gate(
    claim: Claim,
    analysis: ReimbursementAnalysis,
    *,
    pdf_exists: bool = True,
    page_exists: bool = True,
    duplicate_page_reference: bool = False,
) -> FinalDecision:
    """
    Convert an agent recommendation into the final decision.

    The agent may recommend approval, but this function is the
    only place where auto_payable can become True.
    """

    receipt = analysis.receipt

    amount_exact_match = amounts_equal(
        claimed_amount=claim.claimed_amount,
        extracted_amount=receipt.amount,
    )

    date_exact_match = dates_equal(
        claimed_date=claim.expense_date,
        extracted_date=receipt.date,
    )

    if claim.payment_mode in DIGITAL_PAYMENT_MODES:
        transaction_exact_match = identifier_matches_any(
            expected=claim.transaction_id,
            candidates=[
                receipt.transaction_id,
                receipt.utr,
            ],
        )

    else:
        transaction_exact_match = True

    if claim.invoice_no:
        invoice_exact_match = identifier_matches_any(
            expected=claim.invoice_no,
            candidates=[
                receipt.invoice_no,
            ],
        )

    else:
        invoice_exact_match = True

    safety_checks = {
        "pdf_exists": pdf_exists,
        "page_exists": page_exists,
        "unique_page_reference": (
            not duplicate_page_reference
        ),
        "bill_found": receipt.bill_found,
        "receipt_confidence_high": (
            receipt.confidence == "high"
        ),
        "analysis_confidence_high": (
            analysis.analysis_confidence == "high"
        ),
        "amount_exact_match": amount_exact_match,
        "date_exact_match": date_exact_match,
        "vendor_supported_by_agent": (
            analysis.vendor_match is True
        ),
        "payment_mode_not_conflicting": (
            analysis.payment_mode_match is not False
        ),
        "transaction_id_exact_match": (
            transaction_exact_match
        ),
        "invoice_no_exact_match": (
            invoice_exact_match
        ),
        "description_not_conflicting": (
            analysis.description_supported is not False
        ),
        "agent_recommends_approval": (
            analysis.auto_approval_recommended
            and analysis.recommended_status
            == "OK_AUTO_APPROVED"
        ),
    }

    final_status: FinalStatus
    primary_reason: str

    if not pdf_exists:
        final_status = "PDF_MISSING"
        primary_reason = (
            "The monthly PDF file does not exist."
        )

    elif not page_exists:
        final_status = "PAGE_MISSING"
        primary_reason = (
            "The referenced PDF page does not exist."
        )

    elif duplicate_page_reference:
        final_status = "DUPLICATE_PAGE_REFERENCE"
        primary_reason = (
            "The same PDF page is referenced by multiple claims."
        )

    elif not receipt.bill_found:
        final_status = "BILL_NOT_FOUND_ON_PAGE"
        primary_reason = (
            "No valid reimbursement evidence was found "
            "on the referenced page."
        )

    elif (
        receipt.confidence != "high"
        or analysis.analysis_confidence != "high"
    ):
        final_status = "OCR_UNCLEAR"
        primary_reason = (
            "Receipt extraction or claim analysis confidence "
            "is not high."
        )

    elif not amount_exact_match:
        final_status = "AMOUNT_MISMATCH"
        primary_reason = (
            "The claimed amount does not exactly match "
            "the extracted amount."
        )

    elif not date_exact_match:
        final_status = "DATE_MISMATCH"
        primary_reason = (
            "The claim date does not exactly match "
            "the extracted receipt date."
        )

    elif analysis.vendor_match is not True:
        final_status = "VENDOR_MISMATCH"
        primary_reason = (
            "The agent could not confirm that the claim vendor "
            "and extracted merchant are the same."
        )

    elif not transaction_exact_match:
        final_status = "TRANSACTION_ID_MISMATCH"
        primary_reason = (
            "The required transaction ID does not exactly match "
            "the extracted transaction ID or UTR."
        )

    elif not invoice_exact_match:
        final_status = "INVOICE_NO_MISMATCH"
        primary_reason = (
            "The provided invoice number does not exactly match "
            "the extracted invoice number."
        )

    elif (
        analysis.payment_mode_match is False
        or analysis.description_supported is False
        or not analysis.auto_approval_recommended
        or analysis.recommended_status
        != "OK_AUTO_APPROVED"
    ):
        final_status = "POSSIBLE_MATCH_NOT_APPROVED"
        primary_reason = (
            "Some evidence may match, but the complete claim "
            "does not satisfy every approval condition."
        )

    else:
        final_status = "OK_AUTO_APPROVED"
        primary_reason = (
            "All mandatory agent and deterministic safety "
            "checks passed."
        )

    auto_payable = (
        final_status == "OK_AUTO_APPROVED"
        and all(safety_checks.values())
    )

    if not auto_payable and final_status == "OK_AUTO_APPROVED":
        final_status = "POSSIBLE_MATCH_NOT_APPROVED"
        primary_reason = (
            "The agent recommended approval, but at least one "
            "mandatory safety check did not pass."
        )

    final_reasons = [primary_reason]

    final_reasons.extend(
        f"Agent: {reason}"
        for reason in analysis.reasons
    )

    return FinalDecision(
        expense_id=claim.expense_id,
        agent_recommended_status=(
            analysis.recommended_status
        ),
        final_status=final_status,
        auto_payable=auto_payable,
        safety_checks=safety_checks,
        reasons=final_reasons,
    )