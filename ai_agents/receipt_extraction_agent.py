from agents import Agent, RunConfig, Runner

from config import MODEL
from models.receipt import Receipt
from prompts.receipt_prompt import RECEIPT_PROMPT


receipt_extraction_agent = Agent(
    name="Receipt Extraction Agent",
    model=MODEL,
    instructions=RECEIPT_PROMPT,
    output_type=Receipt,
)


def extract_receipt_data(ocr_text: str) -> Receipt:
    """
    Extract structured receipt information from OCR text
    using the OpenAI Agents SDK.

    Only one agent turn is permitted.
    """

    cleaned_text = ocr_text.strip()

    if not cleaned_text:
        raise ValueError(
            "OCR text is empty. Receipt extraction cannot run."
        )

    result = Runner.run_sync(
        starting_agent=receipt_extraction_agent,
        input=(
            "Extract the receipt information from the following OCR text.\n\n"
            f"{cleaned_text}"
        ),
        max_turns=1,
        run_config=RunConfig(
            tracing_disabled=True,
        ),
    )

    receipt = result.final_output

    if not isinstance(receipt, Receipt):
        raise TypeError(
            "Receipt Extraction Agent returned an unexpected output type."
        )

    usage = result.context_wrapper.usage

    print("\n========== OPENAI USAGE ==========\n")
    print(f"Requests: {usage.requests}")
    print(f"Input tokens: {usage.input_tokens}")
    print(f"Output tokens: {usage.output_tokens}")
    print(f"Total tokens: {usage.total_tokens}")

    return receipt