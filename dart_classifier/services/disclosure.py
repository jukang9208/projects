import requests
from core.config import DART_API_KEY
from datetime import datetime, timedelta
from services.financial import lookup_corp_code

LIST_URL = "https://opendart.fss.or.kr/api/list.json"

# report_nm 키워드 → 분류 레이블 (위에 있을수록 우선순위 높음)
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
    # 전환사채 (추가)
    "전환사채":                 "전환사채",
    "교환사채":                 "전환사채",
    "신주인수권부사채":          "전환사채",
    "주요사항보고서[전환사채]":  "전환사채",
    "주요사항보고서[교환사채]":  "전환사채",
    # 자기주식 (추가)
    "자기주식취득":             "자기주식",
    "자기주식처분":             "자기주식",
    "주요사항보고서[자기주식취득]": "자기주식",
    "주요사항보고서[자기주식처분]": "자기주식",
    # 합병·분할 (추가)
    "주요사항보고서[합병]":     "합병·분할",
    "주요사항보고서[분할]":     "합병·분할",
    "주요사항보고서[주식교환]":  "합병·분할",
    "주요사항보고서[영업양수]":  "합병·분할",
    "주요사항보고서[영업양도]":  "합병·분할",
    "합병":                     "합병·분할",
    "분할":                     "합병·분할",
    "영업양수도":               "합병·분할",
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

    results.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)
    return results[:count]


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
        report_nm = filing.get("report_nm", "")
        items.append({
            "rcept_no":     filing.get("rcept_no", ""),
            "rept_nm":      report_nm,
            "rcept_dt":     filing.get("rcept_dt", ""),
            "flr_nm":       filing.get("flr_nm"),
            "label":        classify_by_report_nm(report_nm),
            "score":        None,
            "text_preview": None,
        })

    return {
        "corp_name":  corp_name_,
        "corp_code":  corp_code,
        "stock_code": stock_code,
        "total":      len(items),
        "items":      items,
    }