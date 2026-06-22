import os
import json
import base64
import logging
import holidays
import threading
import firebase_admin
from firebase_admin import credentials, firestore
from core.config import dart_client, GOOGLE_API_KEY
from datetime import datetime, timedelta, timezone, time
from services.ticker_service import find_ticker
from services.dart_service import get_dart_text
from services.news_service import get_news_text
from services.price_service import (
    get_financials,
    get_financial_data_dict,
    get_price_and_indicators,
)
from services.report_service import generate_report
from services.scoring_service import calculate_quant_score
from services.validator_service import validate_and_build_context
from services.macro_indicator_service import get_general_macro_indicators

logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    # 배포 환경: 환경변수(FIREBASE_CREDENTIALS)에 키 JSON이 있으면 그걸로 초기화
    # 로컬 개발: 환경변수가 없으면 serviceAccountKey.json 파일로 fallback
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client(database_id="jukang-llm")

KST = timezone(timedelta(hours=9))

# 동시 요청 방지 락 관리 
_analysis_locks = {}
_locks_lock = threading.Lock()

def _get_analysis_lock(cache_id: str) -> threading.Lock:
    """특정 캐시 ID(종목+관점)에 대한 독립적인 락을 반환합니다."""
    with _locks_lock:
        if cache_id not in _analysis_locks:
            _analysis_locks[cache_id] = threading.Lock()
        return _analysis_locks[cache_id]

def _is_market_open(now_kst: datetime) -> bool:
    """현재 KST 기준 한국 주식 시장 개장 시간인지 확인 (휴장일 완벽 대응)"""
    
    #  주말 체크 
    if now_kst.weekday() >= 5:
        return False
        
    # 한국 법정 공휴일 체크 
    kr_holidays = holidays.KR(years=now_kst.year)
    if now_kst.date() in kr_holidays:
        return False
        
    # 주식 시장 특수 휴장일
    
    if now_kst.month == 5 and now_kst.day == 1:
        return False
    # 연말 폐장일 
    if now_kst.month == 12 and now_kst.day == 31:
        return False

    # 4. 장 시간 체크 (09:00 ~ 15:30)
    market_start = time(9, 0)
    market_end = time(15, 30)
    
    return market_start <= now_kst.time() <= market_end

def _normalize_mode(mode_str: str) -> str:
    """관점 정규화: 단일 분석과 비교 분석 명칭이 달라도 하나의 표준 키워드로 변환"""
    mode_str = mode_str or ""
    if "성장" in mode_str: return "growth"
    if "리스크" in mode_str: return "risk"
    if "밸류" in mode_str or "가치" in mode_str: return "value"
    if "수익" in mode_str: return "profit"
    return "total"

def _encode_safe(text: str) -> str:
    safe_text = "default"
    if text:
        safe_text = base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")
    return safe_text

def _get_cache_id(ticker: str, keyword: str, analysis_mode: str) -> str:
    """정규화된 관점 값을 포함한 최신 캐시용 ID 생성"""
    norm_mode = _normalize_mode(analysis_mode)
    return f"{ticker}_{_encode_safe(keyword)}_{norm_mode}"

def _is_cache_valid(cache_doc) -> bool:
    """시장 운영 시간에 따라 동적으로 캐시 유효성을 검증합니다."""
    if not cache_doc.exists: 
        return False
        
    data = cache_doc.to_dict()
    created_at = data.get("created_at")
    if not created_at: 
        return False

    now_kst = datetime.now(KST)
    
    if getattr(created_at, "tzinfo", None):
        created_at_kst = created_at.astimezone(KST)
    else:
        created_at_kst = created_at.replace(tzinfo=timezone.utc).astimezone(KST)

    if _is_market_open(now_kst):
        logger.info("장중입니다. 3분 TTL을 적용합니다.")
        return (now_kst - created_at_kst) < timedelta(minutes=3)
    else:
        logger.info("장외/휴일입니다. 마지막 캐시를 Fallback으로 사용합니다.")
        return True

def _build_single_response(full_name, ticker, user_focus, analysis_mode, quant_score_data, confidence_score, llm_report, metrics):
    return {
        "name": full_name, "ticker": ticker, "user_focus": user_focus, "analysis_mode": analysis_mode,
        "total_score": quant_score_data.get("total_score", 0),
        "value_score": quant_score_data.get("value_score", 0),
        "profit_score": quant_score_data.get("profit_score", 0),
        "growth_score": quant_score_data.get("growth_score", 0),
        "stability_score": quant_score_data.get("stability_score", 0),
        "risk_score": quant_score_data.get("risk_score", 0),
        "investment_opinion": quant_score_data.get("investment_opinion", "관망"),
        "analysis_summary": quant_score_data.get("analysis_summary", []),
        "raw_metrics": quant_score_data.get("raw_metrics", {}),
        "confidence_score": confidence_score,
        "confidence_value": confidence_score.get("score", 100),
        "confidence_reasons": confidence_score.get("reasons", []),
        "confidence_status": confidence_score.get("status", "정상"),
        "llm_report": llm_report, "metrics": metrics, "quant_score": quant_score_data,
    }

def _read_single_cache(ticker: str, full_name: str, user_focus: str, analysis_mode: str):
    """단일 분석 캐시 조회 (빠른 조회를 위해 최신 컬렉션만 확인)"""
    cache_id = _get_cache_id(ticker, user_focus, analysis_mode)
    cache_ref = db.collection("stock_analysis_latest").document(cache_id)
    cache_doc = cache_ref.get()

    if not _is_cache_valid(cache_doc): 
        return None

    logger.info(f"캐시 적중: {cache_id}")
    data = cache_doc.to_dict()
    return _build_single_response(
        full_name=data.get("company_name", full_name),
        ticker=data.get("ticker", ticker),
        user_focus=data.get("user_focus", user_focus),
        analysis_mode=data.get("analysis_mode", analysis_mode),
        quant_score_data=data.get("quant_detail", {}),
        confidence_score={"score": data.get("confidence_score", 100), "reasons": data.get("confidence_reasons", []), "status": "정상 (캐시됨)"},
        llm_report=data.get("llm_report", {}),
        metrics=data.get("metrics", {})
    )

def _save_single_cache(ticker, full_name, user_focus, analysis_mode, quant_score_data, confidence_score, llm_data, metrics, used_docs_count, force_refresh=False):
    """최신 캐시(전체)와 시계열 히스토리(핵심 지표만) 두 곳에 맞춤형으로 동시 저장"""
    now_kst = datetime.now(KST)
    cache_id = _get_cache_id(ticker, user_focus, analysis_mode)
    latest_ref = db.collection("stock_analysis_latest").document(cache_id)
    
    history_id = f"{cache_id}_{now_kst.strftime('%Y%m%d_%H%M%S')}"
    history_ref = db.collection("stock_analysis_history").document(history_id)
    
    # 서빙용 최신 데이터 페이로드 (전체 포함)
    latest_payload = {
        "ticker": ticker, 
        "company_name": full_name, 
        "quant_score": quant_score_data.get("total_score", 0),
        "quant_detail": quant_score_data, 
        "confidence_score": confidence_score.get("score", 100),
        "confidence_reasons": confidence_score.get("reasons", []),
        "llm_report": llm_data, 
        "user_focus": user_focus, 
        "analysis_mode": analysis_mode,
        "metrics": metrics, 
        "rag_doc_count": used_docs_count, 
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    # 시계열 히스토리용 페이로드 (요청한 구조로 평탄화)
    raw_metrics = quant_score_data.get("raw_metrics", {})
    history_payload = {
        "ticker": ticker,
        "company_name": full_name,
        "user_focus": user_focus,
        "analysis_mode": analysis_mode,
        "normalized_mode": _normalize_mode(analysis_mode),
        "created_at_kst": now_kst.isoformat(),
        
        "confidence_score": confidence_score.get("score", 100),
        "rag_doc_count": used_docs_count,
        "refresh_reason": "force_refresh" if force_refresh else "cache_expired_or_missing",
        
        "total_score": quant_score_data.get("total_score", 0),
        "value_score": quant_score_data.get("value_score", 0),
        "profit_score": quant_score_data.get("profit_score", 0),
        "growth_score": quant_score_data.get("growth_score", 0),
        "stability_score": quant_score_data.get("stability_score", 0),
        "risk_score": quant_score_data.get("risk_score", 0),
        "investment_opinion": quant_score_data.get("investment_opinion", "관망"),
        
        "current_price": metrics.get("current_price"),
        "per": raw_metrics.get("per"),
        "pbr": raw_metrics.get("pbr"),
        "roe": raw_metrics.get("roe"),
        "revenue": metrics.get("revenue"),
        "operating_income": metrics.get("operating_income"),
        "net_income": metrics.get("net_income"),
        
        "revenue_yoy": raw_metrics.get("revenue_yoy"),
        "operating_income_yoy": raw_metrics.get("operating_income_yoy"),
        "net_income_yoy": raw_metrics.get("net_income_yoy")
    }

    batch = db.batch()
    batch.set(latest_ref, latest_payload)
    batch.set(history_ref, history_payload)  # 평탄화된 데이터 저장
    batch.commit()
    
    logger.info(f"데이터 투 트랙 저장 완료: 서빙용({cache_id}), 히스토리용({history_id})")

def run_single_analysis(company_input: str, user_focus: str, analysis_mode: str = "종합 분석", force_refresh: bool = False):
    """단일 기업 분석 파이프라인 (동시성 제어 적용)"""
    ticker, full_name = find_ticker(company_input)
    if not ticker: raise ValueError(f"'{company_input}' 종목을 찾을 수 없습니다.")

    # 락 획득 전 1차 캐시 확인 (빠른 응답)
    if not force_refresh:
        cached = _read_single_cache(ticker, full_name, user_focus, analysis_mode)
        if cached: 
            return cached

    cache_id = _get_cache_id(ticker, user_focus, analysis_mode)
    analysis_lock = _get_analysis_lock(cache_id)

    # 분석용 락 획득
    with analysis_lock:

        # 락 획득 후 2차 캐시 확인 (Double-checked locking)
        if not force_refresh:
            cached_again = _read_single_cache(ticker, full_name, user_focus, analysis_mode)
            if cached_again:
                logger.info(f"동시 요청 대기 후 캐시 적중 (중복 분석 방지됨): {cache_id}")
                return cached_again

        # 신규 분석 수행 영역 
        logger.info(f"신규 분석 수행: {full_name} ({analysis_mode})")
        today_str = datetime.now(KST).strftime("%Y-%m-%d")

        # 데이터 수집 및 전처리
        dart_raw = get_dart_text(dart_client, ticker, full_name)
        news_raw = get_news_text(full_name)
        price_raw = get_price_and_indicators(ticker, dart_client)
        fin_raw = get_financials(ticker, dart_client)
        macro_raw = get_general_macro_indicators()
        fin_dict = get_financial_data_dict(ticker, dart_client)
        quant_score_data = calculate_quant_score(fin_dict)

        valid_data, confidence_score = validate_and_build_context(full_name, dart_raw, news_raw, price_raw, fin_raw, macro_raw)
        llm_context = valid_data.to_llm_context()

        text_corpus = f"[[공시]]\n{llm_context['dart_text']}\n\n[[뉴스]]\n{llm_context['news_text']}"
        fixed_metrics = f"[[정량지표]]\n{llm_context['price_data']}\n{llm_context['financial_data']}\n{llm_context['macro_data']}"
        
        # 리포트 생성
        report_json_str, used_docs = generate_report(
            text_corpus=text_corpus, fixed_metrics=fixed_metrics, company=full_name, google_api_key=GOOGLE_API_KEY,
            user_focus=user_focus, analysis_mode=analysis_mode, today=today_str, 
            confidence_score=confidence_score, quant_score_data=quant_score_data
        )
        llm_data = json.loads(report_json_str)

        # 마지막에 force_refresh 파라미터 추가 전달
        _save_single_cache(
            ticker, full_name, user_focus, analysis_mode, 
            quant_score_data, confidence_score, llm_data, fin_dict, len(used_docs), force_refresh
        )
        
        return _build_single_response(full_name, ticker, user_focus, analysis_mode, quant_score_data, confidence_score, llm_data, fin_dict)


def run_compare_analysis(company_a: str, company_b: str, user_focus: str, analysis_mode: str = "종합 평가 비교", force_refresh: bool = False):
    """비교 분석 파이프라인 (단일 분석 캐시 100% 재사용)"""
    result_a = run_single_analysis(company_a.strip(), user_focus, analysis_mode, force_refresh)
    result_b = run_single_analysis(company_b.strip(), user_focus, analysis_mode, force_refresh)

    return {
        "status": "success", "keyword": user_focus, "analysis_mode": analysis_mode,
        "company_a": result_a, "company_b": result_b,
        "comparison": {
            "company_a_name": result_a.get("name"), "company_b_name": result_b.get("name"),
            "total_score_diff": result_a["total_score"] - result_b["total_score"],
            "better_company": {"winner": result_a["name"] if result_a["total_score"] > result_b["total_score"] else result_b["name"]}
        }
    }