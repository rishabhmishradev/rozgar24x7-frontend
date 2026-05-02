import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env")

client = genai.Client(api_key=api_key)

res = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Return JSON with 3 items",
)

print("FULL RESPONSE OBJECT:")
print(res)

response_text = ""
if hasattr(res, "candidates") and res.candidates:
    for candidate in res.candidates:
        if hasattr(candidate, "content") and candidate.content:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    response_text += part.text
else:
    response_text = str(getattr(res, "text", ""))

print("\nEXTRACTED TEXT:")
print(response_text)
print("\nResponse length:", len(response_text))