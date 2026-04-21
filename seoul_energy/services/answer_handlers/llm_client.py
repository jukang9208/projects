import traceback
from core.config import genai_client

SUMMARY_MODEL = "gemini-2.5-flash"
_HAS_KOREAN = lambda s: any("\uAC00" <= c <= "\uD7A3" for c in s)

def call_llm(prompt: str, fallback: str, handler_name: str = "llm_client") -> str:

    try:
        response = genai_client.models.generate_content(
            model=SUMMARY_MODEL,
            contents=prompt,
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError("빈 응답")
        return text
    except Exception as e:
        print(f"[{handler_name}] LLM 실패 ({type(e).__name__}): {e!r}")
        print(traceback.format_exc())
        return fallback


def clean_rag(docs: list[dict], max_lines: int = 60) -> str:

    lines = []
    for doc in docs:
        for line in doc.get("content", "").split("\n"):
            s = line.strip()
            if s and _HAS_KOREAN(s):
                lines.append(s)
    return "\n".join(lines[:max_lines]) if lines else ""


def filter_rag(docs: list[dict], *districts: str, max_lines: int = 40) -> str:

    lines = []
    for doc in docs:
        for line in doc.get("content", "").split("\n"):
            s = line.strip()
            if not s or not _HAS_KOREAN(s):
                continue
            if any(d in s for d in districts):
                lines.append(s)
    return "\n".join(lines[:max_lines]) if lines else "(보고서 관련 내용 없음)"
