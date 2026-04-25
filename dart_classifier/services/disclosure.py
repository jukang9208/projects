import io
import re
import zipfile
import requests
from bs4 import BeautifulSoup
from core.config import DART_API_KEY
from datetime import datetime, timedelta
from services.classifier import classify_text
from services.financial import lookup_corp_code

LIST_URL     = "https://opendart.fss.or.kr/api/list.json"
DOCUMENT_URL = "https://opendart.fss.or.kr/api/document.json"

# report_nm 키워드 → 분류 레이블
# 우선순위: 위에 있을수록 먼저 매핑
REPORT_NM_MAP = {
    # 정기공시
    "사업보고서":               "사업보고서",
    "반기보고서":               "사업보고서",
    "분기보고서":               "사업보고서",
    # 감사 관련
    "감사보고서":               "감사보고서",
    "감사인":                   "감사보고서",
    "내부회계":                 "감사보고서",
    # 증자 관련
    "유상증자":                 "유상증자",
    "무상증자":                 "유상증자",
    "주요사항보고서[유상증자]":  "유상증자",
    "주요사항보고서[무상증자]":  "유상증자",
    "투자설명서":               "유상증자",
    "신주":                     "유상증자",
}


def classify_by_report_nm(report_nm: str) -> str | None:

    for keyword, label in REPORT_NM_MAP.items():
        if keyword in report_nm:
            return label
    return None


def fetch_disclosure_list(corp_code: str, count: int = 5) -> list[dict]:

    today = datetime.today()
    start = (today - timedelta(days=365)).strftime("%Y%m%d")
    end   = today.strftime("%Y%m%d")

    results = []
    for pblntf_ty in ("A", "B", "F"):
        params = {
            "crtfc_key":  DART_API_KEY,
            "corp_code":  corp_code,
            "bgn_de":     start,
            "end_de":     end,
            "pblntf_ty":  pblntf_ty,
            "page_no":    1,
            "page_count": count,
        }
        res = requests.get(LIST_URL, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "000":
            results.extend(data.get("list", []))

    # 최신순 정렬 후 count 개 반환
    results.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)
    return results[:count]


def fetch_document_text(rcept_no: str) -> str:

    params = {
        "crtfc_key": DART_API_KEY,
        "rcept_no":  rcept_no,
    }
    res = requests.get(DOCUMENT_URL, params=params, timeout=30)
    res.raise_for_status()

    # 응답이 JSON 에러인 경우 처리
    ct = res.headers.get("Content-Type", "")
    if "json" in ct:
        return ""

    try:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            candidates = [
                n for n in z.namelist()
                if n.lower().endswith((".html", ".htm", ".xml"))
                and not n.startswith("__MACOSX")
            ]
            if not candidates:
                return ""

            candidates.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)

            with z.open(candidates[0]) as f:
                raw = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_classified_disclosures(corp_name: str, count: int = 5) -> dict:

    corp = lookup_corp_code(corp_name)
    if not corp:
        raise ValueError(f"'{corp_name}' 기업을 찾을 수 없습니다.")

    corp_code  = corp["corp_code"]
    corp_name_ = corp["corp_name"]
    stock_code = corp.get("stock_code")

    filings = fetch_disclosure_list(corp_code, count)

    items = []
    for filing in filings:
        rcept_no  = filing.get("rcept_no", "")
        report_nm = filing.get("report_nm", "")

        label, score, preview = None, None, None

        # document.json → BERT 분류 시도
        try:
            text = fetch_document_text(rcept_no)
            if text and len(text) >= 10:
                preview = text[:200]
                cls     = classify_text(text[:512])
                label   = cls["label"]
                score   = round(cls["score"], 4)
        except Exception:
            pass

        # 실패 시 report_nm 키워드로 fallback
        if label is None:
            label = classify_by_report_nm(report_nm)

        items.append({
            "rcept_no":     rcept_no,
            "rept_nm":      report_nm,
            "rcept_dt":     filing.get("rcept_dt", ""),
            "flr_nm":       filing.get("flr_nm"),
            "label":        label,
            "score":        score,
            "text_preview": preview,
        })

    return {
        "corp_name":  corp_name_,
        "corp_code":  corp_code,
        "stock_code": stock_code,
        "total":      len(items),
        "items":      items,
    }