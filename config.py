import os

from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY is missing. Add it to your local .env file."
    )

# Development controls
max_pages_value = os.getenv("MAX_PAGES", "1").strip().lower()

if max_pages_value in {"none", "all"}:
    MAX_PAGES = None
else:
    MAX_PAGES = int(max_pages_value)

DRY_RUN = os.getenv(
    "DRY_RUN",
    "true",
).strip().lower() in {"true", "1", "yes", "on"}

# Project folders
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"
CACHE_FOLDER = "cache"