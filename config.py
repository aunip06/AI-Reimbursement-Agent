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

# Development safety
# 1    = process only the first page
# None = process the complete PDF
MAX_PAGES = 1

# Project folders
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"