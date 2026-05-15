from core.model import get_llm
from fastapi import APIRouter, HTTPException
from schemas.ask import AskRequest, AskResponse


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    llm = get_llm()

    user_content = req.question
    if req.context:
        user_content = f"[공시 본문]\n{req.context[:2000]}\n\n[질문]\n{req.question}"

    messages = [
        {"role": "system", "content": "당신은 한국 금융 공시(DART) 전문 AI 어시스턴트입니다. "
                                      "사용자가 제공하는 공시 본문을 바탕으로 핵심 내용을 정확하고 간결하게 한국어로 답변합니다. "
                                      "공시에 없는 내용은 추측하지 않습니다."},
        {"role": "user", "content": user_content},
    ]

    try:
        result = llm.create_chat_completion(
            messages=messages,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            stop=["[|endofturn|]", "</s>"],
        )
        answer = result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AskResponse(answer=answer, question=req.question)
