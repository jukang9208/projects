import logging
from models.schemas import AnalyzeRequest
from fastapi import APIRouter, HTTPException
from services.analyzer import run_single_analysis
from core.config import dart_client, GOOGLE_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def run_analysis(req: AnalyzeRequest):
    
    if not req.company_name:
        raise HTTPException(status_code=400, detail="company_name 누락")

    if not dart_client or not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="API 키 설정 누락")

    try:
        logger.info(
            f"단일 분석 API 호출: {req.company_name} "
            f"(keyword={req.focus_keyword}, analysis_mode={req.analysis_mode}, "
            f"force_refresh={req.force_refresh})"
        )

        result = run_single_analysis(
            company_input=req.company_name,
            user_focus=req.focus_keyword,
            analysis_mode=req.analysis_mode,
            force_refresh=req.force_refresh
        )

        return {
            "company_name": result["name"],
            "ticker": result["ticker"],
            "user_focus": result["user_focus"],
            "analysis_mode": result["analysis_mode"],
            "total_score": result["total_score"],
            "value_score": result["value_score"],
            "profit_score": result["profit_score"],
            "growth_score": result["growth_score"],
            "stability_score": result["stability_score"],
            "risk_score": result["risk_score"],
            "investment_opinion": result["investment_opinion"],
            "analysis_summary": result["analysis_summary"],
            "quant_analysis": result["quant_score"],
            "llm_report": result["llm_report"],
            "metrics": result["metrics"],
            "confidence_score": result["confidence_value"],
            "confidence_reasons": result["confidence_reasons"],
            "confidence_status": result["confidence_status"],
        }

    except ValueError as ve:
        logger.warning(f"단일 분석 요청 오류: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as e:
        logger.error(f"단일 분석 중 서버 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="단일 분석 중 서버 오류가 발생했습니다.")
