import os

from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4.1-mini"      # Change to "gpt-5.5" if you want

# Project folders
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"