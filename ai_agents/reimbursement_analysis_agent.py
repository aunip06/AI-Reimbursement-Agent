import json

from agents import Agent, RunConfig, Runner

from config import MODEL
from models.claim import Claim
from models.reimbursement_analysis import ReimbursementAnalysis
from prompts.reimbursement_analysis_prompt import (
    REIMBURSEMENT_ANALYSIS_PROMPT,
)


reimbursement_analysis_agent = Agent(
    name="Reimbursement Analysis Agent",
    model=MODEL,
    instructions=REIMBURSEMENT_ANALYSIS_PROMPT,
    output_type=ReimbursementAnalysis,
)


def clean_ocr_text(ocr_text: str) -> str:
    """
    Remove empty OCR lines and unnecessary surrounding spaces
    without changing the order of the receipt evidence.
    """

    cleaned_lines = [
        line.strip()
        for line in ocr_text.splitlines()
        if line.strip()
    ]

    return "\n".join(cleaned_lines)


def analyze_reimbursement(
    claim: Claim,
    ocr_text: str,
) -> ReimbursementAnalysis:
    """
    Extract receipt evidence and compare it with one Excel claim
    using one OpenAI Agents SDK model turn.
    """

    cleaned_text = clean_ocr_text(ocr_text)

    if not cleaned_text:
        raise ValueError(
            "OCR text is empty. Reimbursement analysis cannot run."
        )

    claim_json = json.dumps(
        claim.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    )

    agent_input = (
        "Analyze the following reimbursement claim against the OCR "
        "evidence from its referenced PDF page.\n\n"
        "========== EXCEL CLAIM ==========\n"
        f"{claim_json}\n\n"
        "========== OCR EVIDENCE ==========\n"
        f"{cleaned_text}"
    )

    result = Runner.run_sync(
        starting_agent=reimbursement_analysis_agent,
        input=agent_input,
        max_turns=1,
        run_config=RunConfig(
            tracing_disabled=True,
        ),
    )

    analysis = result.final_output

    if not isinstance(
        analysis,
        ReimbursementAnalysis,
    ):
        raise TypeError(
            "Reimbursement Analysis Agent returned an "
            "unexpected output type."
        )

    usage = result.context_wrapper.usage

    print("\n========== OPENAI USAGE ==========\n")
    print(f"Requests: {usage.requests}")
    print(f"Input tokens: {usage.input_tokens}")
    print(f"Output tokens: {usage.output_tokens}")
    print(f"Total tokens: {usage.total_tokens}")

    return analysis