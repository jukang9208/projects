from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from core.spark import get_spark_api
from services.subway_service import UsageService, TransferService, HourlyService

router = APIRouter(prefix="/subway", tags=["subway"])

# Spark 지연 초기화
_spark = None
_usage_svc = None
_transfer_svc = None
_hourly_svc = None


def get_services():
    global _spark, _usage_svc, _transfer_svc, _hourly_svc
    if _spark is None:
        _spark = get_spark_api()
        _usage_svc = UsageService(_spark)
        _transfer_svc = TransferService(_spark)
        _hourly_svc = HourlyService(_spark)
    return _usage_svc, _transfer_svc, _hourly_svc


@router.get("/usage/meta")
def get_meta():
    usage_svc, _, _h = get_services()
    return usage_svc.get_meta()


@router.get("/usage/daily")
def get_daily_usage(
    station: Optional[str] = Query(None, description="역명 (예: 강남)"),
    line:    Optional[str] = Query(None, description="호선 (예: 2호선)"),
):
    usage_svc, _, _h = get_services()
    return usage_svc.get_daily_usage(station, line)


@router.get("/usage/ranking")
def get_top_stations(
    line:  Optional[str] = Query(None, description="호선 필터 (예: 2호선), 생략 시 전체"),
    limit: int           = Query(10,   description="상위 N개 역 (기본 10)"),
):
    usage_svc, _, _h = get_services()
    return usage_svc.get_top_stations(line, limit)


@router.get("/usage/weekly")
def get_weekly_pattern(
    station: str = Query(..., description="역명 (예: 강남)"),
):
    usage_svc, _, _h = get_services()
    return usage_svc.get_weekly_pattern(station)


@router.get("/usage/monthly")
def get_monthly_trend(
    station: str = Query(..., description="역명 (예: 강남)"),
):
    usage_svc, _, _h = get_services()
    return usage_svc.get_monthly_trend(station)


@router.get("/usage/trend")
def get_daily_trend(
    station:    str           = Query(...,  description="역명 (예: 강남)"),
    start_date: Optional[str] = Query(None, description="시작일 (yyyy-MM-dd)"),
    end_date:   Optional[str] = Query(None, description="종료일 (yyyy-MM-dd)"),
):
    usage_svc, _, _h = get_services()
    return usage_svc.get_daily_trend(station, start_date, end_date)


@router.get("/transfer/stations")
def get_transfer_stations():
    _, transfer_svc, _h = get_services()
    return transfer_svc.get_transfer_stations()


@router.get("/transfer/pattern")
def get_transfer_pattern(
    station: str = Query(..., description="환승역명 (예: 신도림)"),
):
    _, transfer_svc, _h = get_services()
    return transfer_svc.get_transfer_pattern(station)


@router.get("/transfer/busiest")
def get_busiest_transfer(
    month: Optional[str] = Query(None, description="월 필터 (예: 2026-05), 생략 시 전체 누적"),
):
    _, transfer_svc, _h = get_services()
    return transfer_svc.get_busiest_transfer(month)


@router.get("/usage/hourly", summary="역별 시간대별 평균 승하차 (0~23시)")
def get_hourly_pattern(
    station: str           = Query(...,  description="역명 (예: 강남)"),
    line:    Optional[str] = Query(None, description="호선 필터 (예: 2호선)"),
    month:   Optional[str] = Query(None, description="월 필터 (예: 2026-05), 생략 시 전체 평균"),
):
    _, _t, hourly_svc = get_services()
    return hourly_svc.get_hourly_pattern(station, line, month)


@router.get("/usage/hourly/peak", summary="역별 피크타임 상위 3시간대")
def get_peak_hours(
    station: str = Query(..., description="역명 (예: 강남)"),
):
    _, _t, hourly_svc = get_services()
    return hourly_svc.get_peak_hours(station)


@router.get("/usage/hourly/ranking", summary="특정 시간대 혼잡 역 TOP N")
def get_rush_hour_ranking(
    hour:  int = Query(8,  description="조회 시각 (0~23). 기본: 오전 8시"),
    limit: int = Query(10, description="상위 N개 역"),
):
    _, _t, hourly_svc = get_services()
    return hourly_svc.get_rush_hour_ranking(hour, limit)


@router.get("/usage/hourly/heatmap", summary="시간대 × 역 히트맵 데이터")
def get_heatmap(
    line: Optional[str] = Query(None, description="호선 필터 (예: 2호선)"),
):
    _, _t, hourly_svc = get_services()
    return hourly_svc.get_heatmap(line)
