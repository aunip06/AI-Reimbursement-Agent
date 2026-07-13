import os

from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4.1-mini"

# Limit pages during development.
# Use None later to process the complete PDF.
MAX_PAGES = 1

# Project folders
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"