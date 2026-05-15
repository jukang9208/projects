from typing import Optional
from fastapi import APIRouter, Query
from core.spark import get_spark_api
from services.subway_service import UsageService, TransferService

router = APIRouter(prefix="/subway", tags=["subway"])

# Spark 지연 초기화 
_spark = None
_usage_svc = None
_transfer_svc = None

def get_services():
    global _spark, _usage_svc, _transfer_svc
    if _spark is None:
        _spark = get_spark_api()
        _usage_svc = UsageService(_spark)
        _transfer_svc = TransferService(_spark)
    return _usage_svc, _transfer_svc

# 일별 승하차량
@router.get("/usage/daily")
def get_daily_usage(
    station: Optional[str] = Query(None, description="역명 (예: 강남)"),
    line:    Optional[str] = Query(None, description="호선 (예: 2호선)"),
):
    usage_svc, _ = get_services()
    return usage_svc.get_daily_usage(station, line)

@router.get("/usage/ranking")
def get_top_stations(
    line:  Optional[str] = Query(None, description="호선 필터 (예: 2호선), 생략 시 전체"),
    limit: int           = Query(10,   description="상위 N개 역 (기본 10)"),
):
    usage_svc, _ = get_services()
    return usage_svc.get_top_stations(line, limit)

@router.get("/usage/weekly")
def get_weekly_pattern(
    station: str = Query(..., description="역명 (예: 강남)"),
):
    usage_svc, _ = get_services()
    return usage_svc.get_weekly_pattern(station)

@router.get("/usage/monthly")
def get_monthly_trend(
    station: str = Query(..., description="역명 (예: 강남)"),
):
    usage_svc, _ = get_services()
    return usage_svc.get_monthly_trend(station)

@router.get("/usage/trend")
def get_daily_trend(
    station:    str           = Query(...,  description="역명 (예: 강남)"),
    start_date: Optional[str] = Query(None, description="시작일 (yyyy-MM-dd)"),
    end_date:   Optional[str] = Query(None, description="종료일 (yyyy-MM-dd)"),
):
    usage_svc, _ = get_services()
    return usage_svc.get_daily_trend(station, start_date, end_date)

# 환승역
@router.get("/transfer/stations")
def get_transfer_stations():
    _, transfer_svc = get_services()
    return transfer_svc.get_transfer_stations()


@router.get("/transfer/pattern")
def get_transfer_pattern(
    station: str = Query(..., description="환승역명 (예: 신도림)"),
):
    _, transfer_svc = get_services()
    return transfer_svc.get_transfer_pattern(station)


@router.get("/transfer/busiest")
def get_busiest_transfer():
    _, transfer_svc = get_services()
    return transfer_svc.get_busiest_transfer()
