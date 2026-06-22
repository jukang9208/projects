import os
import requests
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def clean_html_tags(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def get_news_text(keyword: str) -> str:
    """종목명을 기반으로 네이버 뉴스 검색"""
    logger.info(f"'{keyword}' 관련 뉴스 수집 중...")
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    if not client_id: return "API 키 미설정"

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    # 키워드 뒤에 '주가'를 붙여 관련성 높은 뉴스 유도
    params = {"query": f"{keyword} 주가", "display": 7, "sort": "sim"}

    try:
        response = requests.get(url, headers=headers, params=params)
        items = response.json().get("items", [])
        
        texts = []
        for item in items:
            title = clean_html_tags(item.get("title", ""))
            desc = clean_html_tags(item.get("description", ""))
            texts.append(f"제목: {title}\n요약: {desc}")
            
        return "\n\n".join(texts) if texts else "뉴스 없음"
    except Exception as e:
        logger.error(f"뉴스 수집 실패: {e}")
        return "뉴스 로드 실패"