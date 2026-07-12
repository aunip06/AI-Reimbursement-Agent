from dotenv import load_dotenv
import os
from openai import OpenAI

# Load variables from .env
load_dotenv()

# Read API key
api_key = os.getenv("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=api_key)

# Send a simple request
response = client.responses.create(
    model="gpt-5-mini",
    input="who is narendra modi"
)

print(response.output_text)