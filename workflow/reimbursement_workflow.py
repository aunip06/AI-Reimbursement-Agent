from pydantic import ValidationError

from ai_agents.reimbursement_analysis_agent import (
    analyze_reimbursement,
)
from models.claim import Claim
from models.claim_processing_result import (
    ClaimProcessingResult,
)
from models.reimbursement_analysis import (
    ReimbursementAnalysis,
)
from tools.approval_tool import (
    apply_approval_safety_gate,
)
from tools.cache_tool import (
    load_cached_analysis_result,
    save_cached_analysis_result,
)


def process_claim_ocr(
    claim: Claim,
    ocr_text: str,
    *,
    pdf_exists: bool = True,
    page_exists: bool = True,
    duplicate_page_reference: bool = False,
) -> ClaimProcessingResult:
    """
    Process one reimbursement claim using prepared OCR evidence.

    Workflow:
    1. Validate the OCR text.
    2. Check the claim-aware local cache.
    3. Use a valid cached SDK result when available.
    4. Otherwise perform one OpenAI Agents SDK analysis.
    5. Save the successful analysis to cache.
    6. Apply the final non-overridable safety gate.
    """

    cleaned_ocr_text = ocr_text.strip()

    if not cleaned_ocr_text:
        raise ValueError(
            "OCR text is empty. Claim processing cannot continue."
        )

    cached_data = load_cached_analysis_result(
        claim=claim,
        ocr_text=cleaned_ocr_text,
    )

    analysis: ReimbursementAnalysis | None = None
    result_source: str

    if cached_data is not None:
        try:
            analysis = ReimbursementAnalysis.model_validate(
                cached_data
            )

        except ValidationError:
            # Ignore stale, damaged, or incompatible cache data.
            analysis = None

        else:
            result_source = "cache"

    if analysis is None:
        analysis = analyze_reimbursement(
            claim=claim,
            ocr_text=cleaned_ocr_text,
        )

        save_cached_analysis_result(
            claim=claim,
            ocr_text=cleaned_ocr_text,
            result=analysis.model_dump(
                mode="json"
            ),
        )

        result_source = "openai"

    final_decision = apply_approval_safety_gate(
        claim=claim,
        analysis=analysis,
        pdf_exists=pdf_exists,
        page_exists=page_exists,
        duplicate_page_reference=(
            duplicate_page_reference
        ),
    )

    return ClaimProcessingResult(
        expense_id=claim.expense_id,
        result_source=result_source,
        analysis=analysis,
        final_decision=final_decision,
        message=(
            "Claim analysis completed and the final "
            "approval safety gate was applied."
        ),
    )