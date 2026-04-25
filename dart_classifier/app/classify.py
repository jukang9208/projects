import torch
import traceback
from fastapi import APIRouter, HTTPException
from services.classifier import classify_text
from schemas.classify import ClassifyRequest, ClassifyResponse, ClassifyResult

router = APIRouter(prefix="/classify", tags=["분류"])

@router.post("", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest):

    try:
        result = classify_text(request.text)
        return ClassifyResponse(
            result=ClassifyResult(label=result["label"], score=result["score"]),
            text_length=len(request.text),
        )
    except Exception as e:

        print("--- 에러 상세 정보 시작 ---")
        print(traceback.format_exc()) 
        print("--- 에러 상세 정보 끝 ---")
        raise HTTPException(status_code=500, detail=str(e))