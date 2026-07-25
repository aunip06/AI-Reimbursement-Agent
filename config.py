"""Central configuration for the reimbursement application.

Environment variables are loaded from the local `.env` file.
Secrets must never be committed to Git.
"""

import os

from dotenv import load_dotenv


load_dotenv()


# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is missing. "
        "Add it to your local .env file."
    )


# Runtime folders
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"
CACHE_FOLDER = "cache"