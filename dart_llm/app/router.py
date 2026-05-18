import torch
from core.model import get_llm
from fastapi import APIRouter, HTTPException
from schemas.ask import AskRequest, AskResponse


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    model, tokenizer = get_llm()  # 튜플 언팩

    user_content = req.question
    if req.context:
        user_content = f"[공시 본문]\n{req.context[:4000]}\n\n[질문]\n{req.question}"

    messages = [
        {"role": "system", "content": "당신은 한국 금융 공시(DART) 전문 AI 어시스턴트입니다. "
                                      "사용자가 제공하는 공시 본문을 바탕으로 핵심 내용을 정확하고 간결하게 한국어로 답변합니다. "
                                      "공시에 없는 내용은 추측하지 않습니다."},
        {"role": "user", "content": user_content},
    ]

    try:
        inputs = tokenizer.apply_chat_template(
            messages, return_tensors='pt', add_generation_prompt=True
        )
        if isinstance(inputs, dict) or hasattr(inputs, 'input_ids'):
            input_ids = inputs['input_ids'].to(model.device)
        else:
            input_ids = inputs.to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                input_ids,
                max_new_tokens=req.max_tokens,
                temperature=req.temperature,
                do_sample=req.temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.3,
                no_repeat_ngram_size=0,
            )

        answer = tokenizer.decode(
            outputs[0][input_ids.shape[1]:],
            skip_special_tokens=True
        ).strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AskResponse(answer=answer, question=req.question)
