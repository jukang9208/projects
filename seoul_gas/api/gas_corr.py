from fastapi import APIRouter
from core.config import supabase
from services.analysis_service import EnergyAnalysisService

router = APIRouter()

analysis_service = EnergyAnalysisService(supabase)


@router.get("/corr")
def get_correlation():
    return analysis_service.get_correlation_data()