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
        # Measured reality: phi3:mini on this 2-vCPU host generates ~2 tokens/sec,
        # so 350 tokens = ~176s. Since generation is now fully background (never
        # tied to an HTTP request or login), we can afford a generous ceiling.
        # 250 tokens keeps the typical run near ~125s while still giving a full
        # 4-part answer; 360s ceiling absorbs cold-start reload + variance.
        async with httpx.AsyncClient(timeout=360) as client:
            resp = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": m, "prompt": prompt, "stream": False,
                      # Ollama unloads the model after 5min idle by default. Keep
                      # it warm for 2h so back-to-back generations skip the reload.
                      "keep_alive": "2h",
                      "options": {"temperature": 0.3, "num_predict": 250}}
            )
            resp.raise_for_status()
            return resp.json().get("response", "No response from model.")
    except Exception as e:
        detail = str(e) or f"{type(e).__name__} (no message — likely a timeout waiting for the model to finish generating)"
        return f"⚠️ AI analysis unavailable: {detail}\n\nEnsure Ollama is running and the model is pulled."

async def stream_analyse(context: str, model: str = None, prompt_type: str = "daily_insight"):
    m = model or settings.OLLAMA_MODEL
    prompt = build_prompt(context, prompt_type)
    import json
    async with httpx.AsyncClient(timeout=240) as client:
        async with client.stream(
            "POST", f"{settings.OLLAMA_URL}/api/generate",
            json={"model": m, "prompt": prompt, "stream": True,
                  "keep_alive": "30m",
                  "options": {"temperature": 0.3, "num_predict": 350}}
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
