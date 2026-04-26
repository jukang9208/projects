import re
import requests
from core.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"


def _strip_html(text: str) -> str:

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def fetch_news(corp_name: str, display: int = 10) -> list[dict]:

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query":   corp_name,
        "display": display,
        "sort":    "date",
    }

    res = requests.get(NEWS_URL, headers=headers, params=params, timeout=10)
    res.raise_for_status()

    return [
        {
            "title":       _strip_html(item.get("title", "")),
            "link":        item.get("link", ""),
            "pub_date":    item.get("pubDate", ""),
            "description": _strip_html(item.get("description", "")),
        }
        for item in res.json().get("items", [])
    ]