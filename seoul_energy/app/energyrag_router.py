import traceback
from fastapi import APIRouter, HTTPException
from services.answer_service import answer_question
from schemas.schemas import QueryRequest, QueryResponse

router = APIRouter()

@router.post("/rag", response_model=QueryResponse)
def ask_rag(request : QueryRequest):
    try :
        result = answer_question(request.question)
        return QueryResponse(**result)

    except Exception as e:
        print(f"RAG endpoint error: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")