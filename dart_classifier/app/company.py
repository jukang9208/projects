from datetime import datetime
from services.news import fetch_news
from services.financial import get_financial
from services.sentiment import analyze_sentiment
from fastapi import APIRouter, HTTPException, Query
from services.disclosure import get_classified_disclosures
from schemas.classify import (
    CompanyResponse, DisclosureItem,
    NewsSentiment, NewsArticle, FinancialData,
)

router = APIRouter(prefix="/company", tags=["기업 종합 조회"])


def _empty_financial(corp_name: str, year: int) -> dict:
    return {
        "corp_name": corp_name, "stock_code": None, "year": year,
        "revenue": None, "operating_profit": None, "net_income": None,
        "total_assets": None, "total_liabilities": None, "total_equity": None,
        "debt_ratio": None, "close": None, "market_cap": None,
        "high_52w": None, "low_52w": None, "listed": False, "source": "no_data",
    }


def _empty_sentiment() -> dict:
    return {
        "label": "중립",
        "positive_ratio": 0.0,
        "negative_ratio": 0.0,
        "neutral_ratio": 0.0,
        "articles": [],
    }


@router.get("/debug/sentiment")
async def debug_sentiment(corp_name: str = Query("삼성전자")):
    """감성분석 파이프라인 전체 테스트"""
    try:
        articles = fetch_news(corp_name, 3)
        result = analyze_sentiment(articles)
        return {"ok": True, "article_count": len(articles), "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}


@router.get("/debug/news")
async def debug_news(corp_name: str = Query("삼성전자")):
    """뉴스 API 연결 상태 확인용 임시 엔드포인트"""
    import os
    from core.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
    import requests as req

    key_set = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)
    if not key_set:
        return {"key_set": False, "error": "NAVER 환경변수 미설정"}

    try:
        res = req.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": corp_name, "display": 3, "sort": "date"},
            timeout=10,
        )
        return {
            "key_set":    True,
            "status_code": res.status_code,
            "response":   res.json(),
        }
    except Exception as e:
        return {"key_set": True, "error": str(e)}


@router.get("", response_model=CompanyResponse)
async def get_company(
    corp_name:        str = Query(...,  description="기업명 (예: 삼성전자)"),
    news_count:       int = Query(10,   ge=1, le=20, description="조회할 뉴스 수"),
    disclosure_count: int = Query(5,    ge=1, le=20, description="조회할 공시 수"),
):

    try:
        # 공시 목록 조회
        disc = get_classified_disclosures(corp_name, disclosure_count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 뉴스 감성분석
    sentiment_error = None
    try:
        articles = fetch_news(corp_name, news_count)
        sentiment_raw = analyze_sentiment(articles)
    except Exception as e:
        sentiment_error = str(e)
        sentiment_raw = _empty_sentiment()

    # 재무제표 
    year = datetime.today().year - 1
    try:
        fin_raw = get_financial(corp_name, year)
    except Exception:
        fin_raw = _empty_financial(corp_name, year)

    return CompanyResponse(
        corp_name=disc["corp_name"],
        corp_code=disc["corp_code"],
        stock_code=disc["stock_code"],
        disclosures=[DisclosureItem(**item) for item in disc["items"]],
        news_sentiment=NewsSentiment(
            **{k: v for k, v in sentiment_raw.items() if k != "articles"},
            articles=[NewsArticle(**a) for a in sentiment_raw["articles"]],
        ),
        financial=FinancialData(**fin_raw),
    )