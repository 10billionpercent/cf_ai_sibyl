import fitz
import httpx
import json
import os

from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

PROMPT_PATH = Path("prompts/resume_prompt.txt")

async def get_embedding(text):

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5"

    async with httpx.AsyncClient(timeout=60) as client:

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "text": text
            }
        )

    result = response.json()

    return result["result"]["data"][0]

def extract_text(pdf_bytes):

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    text = ""

    for page in doc:
        text += page.get_text()

    return text


async def call_llm(resume_text):

    prompt = PROMPT_PATH.read_text()

    full_prompt = f"""
{prompt}

Resume:

{resume_text}
"""

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-70b-instruct"


    async with httpx.AsyncClient(timeout=60) as client:

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a resume parser. Return JSON only."
                    },
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                "temperature": 0
            }
        )

    result = response.json()

    # DEBUG (optional but helpful)
    print("Cloudflare response:", result)
    
    content = result["result"]["response"]

    content = content.strip()

    if content.startswith("```"):
        content = content.strip("`")
        content = content.replace("json", "").strip()

    return json.loads(content)


async def parse_resume(pdf_bytes):

    text = extract_text(pdf_bytes)

    parsed = await call_llm(text)

    # create summary text
    summary_text = f"""
Role: {parsed.get("role")}
Skills: {parsed.get("skills")}
Preferences: {parsed.get("preferences")}
Technologies: {parsed.get("technologies")}
"""

    embedding = await get_embedding(summary_text)

    parsed["embedding"] = embedding

    return parsed