import httpx
import pathlib
import functools
from app.config import settings

SYSTEM_PROMPT = """You are the AI Sales Intelligence engine for WEPSol FluidPro — India's leading B2B IT Managed Services company (www.wepsol.com).
You analyse field sales data using BANT methodology (Budget, Authority, Need, Timeline).
Be concise, structured, and actionable. Use emoji headers. Output clean markdown.
Focus on the Indian enterprise IT market: BFSI, Manufacturing, Healthcare, Education verticals."""

PROMPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "prompts"

@functools.lru_cache(maxsize=None)
def load_prompt(prompt_type: str) -> str:
    path = PROMPTS_DIR / f"{prompt_type}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

def build_prompt(context: str, prompt_type: str) -> str:
    template = load_prompt(prompt_type)
    parts = [SYSTEM_PROMPT]
    if template:
        parts.append(template)
    parts.append(f"---\nDATA TO ANALYSE:\n{context}\n---")
    return "\n\n".join(parts)

async def analyse(context: str, model: str = None, prompt_type: str = "daily_insight") -> str:
    m = model or settings.OLLAMA_MODEL
    prompt = build_prompt(context, prompt_type)
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": m, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.3, "num_predict": 600}}
            )
            resp.raise_for_status()
            return resp.json().get("response", "No response from model.")
    except Exception as e:
        return f"⚠️ AI analysis unavailable: {str(e)}\n\nEnsure Ollama is running and the model is pulled."

async def stream_analyse(context: str, model: str = None, prompt_type: str = "daily_insight"):
    m = model or settings.OLLAMA_MODEL
    prompt = build_prompt(context, prompt_type)
    import json
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", f"{settings.OLLAMA_URL}/api/generate",
            json={"model": m, "prompt": prompt, "stream": True,
                  "options": {"temperature": 0.3, "num_predict": 600}}
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if chunk.get("done"):
                            yield "data: [DONE]\n\n"
                            break
                    except Exception:
                        continue
