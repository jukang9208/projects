import logging
import OpenDartReader
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def clean_html(raw_html: str) -> str:
    """HTML/XML 태그를 제거하고 순수 텍스트만 추출합니다."""
    if not raw_html: return ""
    soup = BeautifulSoup(raw_html, "lxml-xml")
   
    return soup.get_text(separator=" ", strip=True)

def get_dart_text(dart_client: OpenDartReader, ticker_full: str, company_name: str) -> str:
    ticker = ticker_full[:6]
    logger.info(f"'{company_name}({ticker})' 공시 데이터 수집 중 ...")

    try:
        df = dart_client.list(ticker, start="20240101")
        if df is None or df.empty:
            return "최근 공시 내역이 없습니다."

        important_keywords = ["사업보고서", "반기보고서", "분기보고서", "매출액또는손익구조", "영업(잠정)실적"]
        filtered = df[df["report_nm"].astype(str).apply(lambda x: any(k in x for k in important_keywords))]

        filtered = filtered.head(1) if not filtered.empty else df.head(1)
        
        texts = []
        for _, row in filtered.iterrows():
            try:
                doc_html = dart_client.document(row["rcept_no"])
                if doc_html:
                    
                    clean_text = clean_html(doc_html)
                    texts.append(f"[공시명] {row['report_nm']}\n{clean_text[:5000]}")
            except Exception as e:
                logger.warning(f"공시 본문 수집 실패: {e}")
        
        return "\n\n".join(texts) if texts else "공시 본문을 가져오지 못했습니다."
    except Exception as e:
        logger.error(f"공시 오류 상세: {e}")
        return "공시 데이터를 불러오지 못했습니다."