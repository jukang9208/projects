import logging
from models.schemas import CompareRequest
from fastapi import APIRouter, HTTPException
from services.analyzer import run_compare_analysis
from core.config import dart_client, GOOGLE_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/compare")
def compare_companies(req: CompareRequest):
    
    if not dart_client or not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="서버 API 키 설정이 누락되었습니다.")

    try:
        
        keyword = req.focus_keyword
        mode = req.compare_focus
        force_refresh = req.force_refresh

        logger.info(
            f"기업 비교 분석 API 호출: {req.company_a} vs {req.company_b} "
            f"(keyword={keyword}, mode={mode}, force_refresh={force_refresh})"
        )

        # analyzer 엔진의 run_compare_analysis 호출
        result = run_compare_analysis(
            company_a=req.company_a,
            company_b=req.company_b,
            user_focus=keyword,
            analysis_mode=mode, 
            force_refresh=force_refresh
        )

        return result

    except ValueError as ve:
        logger.warning(f"비교 분석 요청 오류: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        logger.error(f"서버 내부 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="비교 분석 중 서버 오류가 발생했습니다.")