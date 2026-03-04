import json
import time
import httpx
from src.config import Config
from src.models import AuditRequest, AuditReport
from src.prompts import (
    GEMINI_SYSTEM_PROMPT,
    GROQ_SYSTEM_PROMPT,
    build_gemini_user_prompt,
    build_groq_user_prompt,
)
from src.token_tracker import gemini_limiter, groq_limiter
from src.search_tool  import fetch_snippets

async def get_audit_report(request: AuditRequest) -> AuditReport:
    if gemini_limiter.can_send():
        try:
            result = await _call_gemini(request)
            gemini_limiter.record()
            return _parse_response(result, model_used="gemini")
        except Exception as e:
            print(f"[WARNING] Gemini call failed: {str(e)} -- falling back to Groq.")

    else:
        wait = gemini_limiter.wait_time()
        print(f"[INFO] Gemini RPM limit reached. Waiting {wait:.1f} seconds. Falling back to Groq.")

    if groq_limiter.can_send():
        try:
            snippets = fetch_snippets(request.business_name, request.city, request.facebook_url)
            print(f"[INFO] Fetched {snippets.count('[SOURCE]')} DDG snippets for Groq context")

            result = await _call_groq(request, snippets)
            groq_limiter.record()
            return _parse_response(result, model_used="groq")
        except Exception as e:
            print(f"[ERROR] Groq also failed: {str(e)}")
    else:
        wait = groq_limiter.wait_time()
        print(f"[WARN] Both models rate-limited. Waiting {wait:.1f}s for Groq...")
        time.sleep(wait + 0.5)
        groq_limiter.record()
        snippets = fetch_snippets(request.business_name, request.city, request.facebook_url)
        result = await _call_groq(request, snippets)
        return _parse_response(result, model_used="groq")
    
async def _call_gemini(request: AuditRequest) -> str:
    url = f"{Config.GEMINI_BASE_URL}/{Config.GEMINI_MODEL}:generateContent"

    user_prompt = build_gemini_user_prompt(
        request.business_name, request.city, request.facebook_url
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": GEMINI_SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [{"text": user_prompt}]
            }
        ],

        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            json=payload,
            params={"key": Config.GEMINI_API_KEY}
        )
        response.raise_for_status()
        data = response.json()

    try:
        return data["candiates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response structure: {e}\nRaw: {data}")
    
async def _call_groq(request: AuditRequest, search_context: str) -> str:
    system_prompt_with_context = GROQ_SYSTEM_PROMPT.format(search_context=search_context)

    user_prompt = build_groq_user_prompt(request.business_name, request.city)

    payload = {
        "model": Config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt_with_context},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2048
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            Config.GROQ_BASE_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        Data = response.json()
    
    return Data["choices"][0]["message"]["content"]

def _parse_response(raw_text: str, mode_used: str) -> AuditReport:
    
    text = raw_text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON: {e}\n"
            f"Raw response:\n{raw_text[:500]}"
        )
    
    data["model_used"] = mode_used

    return AuditReport(**data)