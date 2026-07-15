from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PDFPage(BaseModel):
    """
    Metadata for one rendered PDF page.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    source_file: str = Field(
        description="Original PDF filename."
    )

    page_number: int = Field(
        ge=1,
        description="One-based page number in the PDF."
    )

    image_path: Path = Field(
        description="Local path of the rendered page image."
    )
    