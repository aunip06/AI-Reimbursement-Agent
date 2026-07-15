from pydantic import ValidationError

from ai_agents.reimbursement_analysis_agent import (
    analyze_reimbursement,
)
from config import DRY_RUN
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
    dry_run: bool | None = None,
) -> ClaimProcessingResult:
    """
    Process one claim against OCR evidence from its mapped PDF page.

    Workflow:
    1. Check the claim-aware cache.
    2. Use the cached analysis when valid.
    3. Respect DRY_RUN when no cache exists.
    4. Otherwise run one OpenAI Agents SDK analysis.
    5. Apply the non-overridable approval safety gate.
    """

    effective_dry_run = (
        DRY_RUN
        if dry_run is None
        else dry_run
    )

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
            # Ignore stale or incompatible cache data.
            analysis = None

        else:
            result_source = "cache"

    if analysis is None:
        if effective_dry_run:
            return ClaimProcessingResult(
                expense_id=claim.expense_id,
                result_source="dry_run",
                analysis=None,
                final_decision=None,
                message=(
                    "No valid cached analysis was found. "
                    "OpenAI analysis was skipped because DRY_RUN=true."
                ),
            )

        analysis = analyze_reimbursement(
            claim=claim,
            ocr_text=cleaned_ocr_text,
        )

        save_cached_analysis_result(
            claim=claim,
            ocr_text=cleaned_ocr_text,
            result=analysis.model_dump(mode="json"),
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