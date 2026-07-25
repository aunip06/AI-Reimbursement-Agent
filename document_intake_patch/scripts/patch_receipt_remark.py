from __future__ import annotations

from pathlib import Path


RECEIPT_PATH = Path("models/receipt.py")
PROMPT_PATH = Path("prompts/receipt_prompt.py")
CACHE_PATH = Path("tools/cache_tool.py")


REMARK_FIELD = '''
    remark: str | None = Field(
        default=None,
        description=(
            "Short purpose or description visible in the receipt, "
            "such as taxi fare, hotel stay, printing, meal, or supplies."
        ),
    )

'''

REMARK_PROMPT = '''
remark:
- Extract a short purpose or description that is visibly supported by the
  receipt, such as taxi fare, hotel stay, printing, meal, office supplies,
  fuel, courier, or travel ticket.
- Do not use generic payment states such as Paid or Successful as the remark
  when a more useful bill purpose is visible.
- Return null when the purpose is not visible. Do not infer it only from the
  merchant name.

'''


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".before_pdf_intake")

    if not backup_path.exists():
        backup_path.write_text(
            path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def patch_receipt_model() -> None:
    source = RECEIPT_PATH.read_text(encoding="utf-8")

    if "    remark: str | None = Field(" in source:
        print("Receipt remark field already present.")
        return

    marker = "    confidence: Literal[\n"

    if marker not in source:
        raise RuntimeError("Receipt confidence field marker was not found.")

    backup(RECEIPT_PATH)
    source = source.replace(marker, REMARK_FIELD + marker, 1)
    RECEIPT_PATH.write_text(source, encoding="utf-8")
    print("Added Receipt.remark.")


def patch_receipt_prompt() -> None:
    source = PROMPT_PATH.read_text(encoding="utf-8")

    if "remark:\n- Extract a short purpose" in source:
        print("Receipt remark prompt already present.")
        return

    marker = "confidence:\nChoose exactly one:\n"

    if marker not in source:
        raise RuntimeError("Receipt prompt confidence marker was not found.")

    backup(PROMPT_PATH)
    source = source.replace(marker, REMARK_PROMPT + marker, 1)
    PROMPT_PATH.write_text(source, encoding="utf-8")
    print("Added receipt remark prompt guidance.")


def patch_receipt_cache_version() -> None:
    source = CACHE_PATH.read_text(encoding="utf-8")

    if 'RECEIPT_CACHE_VERSION = "receipt-extraction-v3"' in source:
        print("Receipt cache version already updated.")
        return

    old_value = 'RECEIPT_CACHE_VERSION = "receipt-extraction-v2"'

    if old_value not in source:
        raise RuntimeError("Expected receipt cache version was not found.")

    backup(CACHE_PATH)
    source = source.replace(
        old_value,
        'RECEIPT_CACHE_VERSION = "receipt-extraction-v3"',
        1,
    )
    CACHE_PATH.write_text(source, encoding="utf-8")
    print("Updated receipt extraction cache version to v3.")


def main() -> None:
    patch_receipt_model()
    patch_receipt_prompt()
    patch_receipt_cache_version()
    print("Document-intake receipt schema patch completed.")


if __name__ == "__main__":
    main()
