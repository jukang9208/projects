from typing import Any
from services.answer_utils import to_python_type
from services.db_service import seararch_rag_documents
from services.answer_handlers.llm_client import call_llm, clean_rag

_GENERAL_PROMPT = """당신은 서울시 에너지 데이터 분석 전문가입니다.
아래 [보고서 내용]을 바탕으로 질문에 대해 3~4문장으로 답하세요.

규칙:
- 보고서 내용에 있는 수치와 인사이트를 활용
- 차트 눈금, 반복 문장은 무시
- 한국어, 존댓말 금지, 답변만 출력

[질문]
{question}

[보고서 내용]
{rag_text}
"""

def answer_general(question: str) -> dict[str, Any]:
    docs = to_python_type(seararch_rag_documents(question, match_count=5))
    rag_text = clean_rag(docs)

    if not rag_text:
        return {
            "intent": "general",
            "answer": "질문에 해당하는 분석 내용을 찾지 못했습니다.",
            "docs": docs,
            "sources": docs,
        }

    prompt = _GENERAL_PROMPT.format(question=question, rag_text=rag_text)
    answer = call_llm(prompt, fallback=rag_text[:300], handler_name="general_handler")

    return {
        "intent":  "general",
        "answer":  answer,
        "docs":    docs,
        "sources": docs,
    }
