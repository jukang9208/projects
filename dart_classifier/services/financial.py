import os
import requests
from services.embedder import embed_text
from services.market import get_market_data
from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY, DART_API_KEY

FINANCIAL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"


# account_nm 기반 매핑 (표기 변형 포함)
TARGET_ACCOUNTS = {
    "매출액":           "revenue",
    "수익(매출액)":     "revenue",
    "영업수익":         "revenue",
    "매출":             "revenue",
    "영업이익":         "operating_profit",
    "영업이익(손실)":   "operating_profit",
    "당기순이익":       "net_income",
    "당기순이익(손실)": "net_income",
    "연결당기순이익":   "net_income",
    "당기순손익":       "net_income",
    "자산총계":         "total_assets",
    "자산 합계":        "total_assets",
    "부채총계":         "total_liabilities",
    "부채 합계":        "total_liabilities",
    "자본총계":         "total_equity",
    "자본 합계":        "total_equity",
}

# account_id 기반 매핑 (IFRS 표준 — 계정명이 달라도 안정적)
TARGET_ACCOUNT_IDS = {
    "ifrs-full_Revenue":                                "revenue",
    "ifrs_Revenue":                                     "revenue",
    "dart_Revenue":                                     "revenue",
    "dart_OperatingIncomeLoss":                         "operating_profit",
    "ifrs-full_ProfitLoss":                             "net_income",
    "ifrs-full_ProfitLossAttributableToOwnersOfParent": "net_income",
    "ifrs-full_Assets":                                 "total_assets",
    "ifrs-full_Liabilities":                            "total_liabilities",
    "ifrs-full_Equity":                                 "total_equity",
    "ifrs-full_EquityAttributableToOwnersOfParent":     "total_equity",
}

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def lookup_corp_code(corp_name: str) -> dict | None:
    client = get_client()

    # 정확한 이름 + 상장사 우선 (동명 법인 중 상장사 선택)
    exact_listed = (
        client.table("dart_corps")
        .select("corp_code, corp_name, stock_code")
        .eq("corp_name", corp_name)
        .not_.is_("stock_code", "null")
        .limit(1)
        .execute()
    )
    if exact_listed.data:
        return exact_listed.data[0]

    # 정확한 이름 (비상장 포함)
    exact = (
        client.table("dart_corps")
        .select("corp_code, corp_name, stock_code")
        .eq("corp_name", corp_name)
        .limit(1)
        .execute()
    )
    if exact.data:
        return exact.data[0]

    # 부분 일치 - 상장사 우선
    partial = (
        client.table("dart_corps")
        .select("corp_code, corp_name, stock_code")
        .ilike("corp_name", f"%{corp_name}%")
        .not_.is_("stock_code", "null")
        .limit(1)
        .execute()
    )
    if partial.data:
        return partial.data[0]

    # 부분 일치 - 비상장 포함
    fallback = (
        client.table("dart_corps")
        .select("corp_code, corp_name, stock_code")
        .ilike("corp_name", f"%{corp_name}%")
        .limit(1)
        .execute()
    )
    return fallback.data[0] if fallback.data else None


def fetch_financial_from_dart(corp_code: str, year: int) -> dict | None:
    """
    DART fnlttSinglAcntAll 조회. 8개 COMBO fallback.
    데이터 없으면 None 반환 (비상장사·미공시 포함).
    """
    # fnlttSinglAcntAll 은 fs_div 필수 — CFS(연결) 우선, OFS(별도) fallback
    # reprt_code: 사업보고서(11011) 우선, 반기·분기 순으로 fallback
    COMBOS = [
        ("11011", "CFS"),
        ("11011", "OFS"),
        ("11012", "CFS"),
        ("11012", "OFS"),
        ("11013", "CFS"),
        ("11013", "OFS"),
        ("11014", "CFS"),
        ("11014", "OFS"),
    ]

    data = None
    for reprt_code, fs_div in COMBOS:
        params = {
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        }
        res = requests.get(FINANCIAL_URL, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "000":
            break

    # 8개 COMBO 전부 실패 — 비상장사 또는 미공시
    if data is None or data.get("status") != "000":
        return None

    # fs_div를 요청 파라미터로 이미 지정했으므로 응답 그대로 사용
    items = data.get("list", [])
    targets = items

    all_keys = set(TARGET_ACCOUNTS.values()) | set(TARGET_ACCOUNT_IDS.values())
    financials: dict[str, int | None] = {v: None for v in all_keys}

    for item in targets:
        acct_nm = item.get("account_nm", "").strip()
        acct_id = item.get("account_id", "").strip()

        # account_nm 우선, 없으면 account_id로 매핑
        key = TARGET_ACCOUNTS.get(acct_nm) or TARGET_ACCOUNT_IDS.get(acct_id)
        if not key:
            continue
        if financials.get(key) is not None:
            continue  # 중복 방지 (먼저 매핑된 값 유지)

        raw = item.get("thstrm_amount", "").replace(",", "").strip()
        try:
            financials[key] = int(raw)
        except (ValueError, AttributeError):
            financials[key] = None

    return financials


def build_summary(corp_name: str, year: int, f: dict) -> str:

    def fmt(v):
        if v is None:
            return "정보없음"
        billion = v / 1_0000_0000
        return f"{billion:,.1f}억원"

    debt_ratio = None
    if f["total_liabilities"] and f["total_equity"] and f["total_equity"] != 0:
        debt_ratio = round(f["total_liabilities"] / f["total_equity"] * 100, 1)

    lines = [
        f"{corp_name}의 {year}년 재무현황",
        f"매출액: {fmt(f['revenue'])}",
        f"영업이익: {fmt(f['operating_profit'])}",
        f"당기순이익: {fmt(f['net_income'])}",
        f"자산총계: {fmt(f['total_assets'])}",
        f"부채총계: {fmt(f['total_liabilities'])}",
        f"자본총계: {fmt(f['total_equity'])}",
        f"부채비율: {f'{debt_ratio}%' if debt_ratio is not None else '정보없음'}",
    ]
    return "\n".join(lines)


def save_financial(corp_code: str, corp_name: str, stock_code: str | None,
                   year: int, financials: dict) -> None:
    
    summary = build_summary(corp_name, year, financials)
    embedding = embed_text(summary)

    debt_ratio = None
    if financials.get("total_liabilities") and financials.get("total_equity") and financials["total_equity"] != 0:
        debt_ratio = round(financials["total_liabilities"] / financials["total_equity"] * 100, 1)

    row = {
        "chunk_id": f"{corp_code}_{year}",
        "doc_id":   corp_code,
        "title":    f"{corp_name} {year}년 재무현황",
        "section":  "재무제표",
        "content":  summary,
        "metadata": {
            "corp_name":  corp_name,
            "corp_code":  corp_code,
            "stock_code": stock_code,   # 주가 조회용으로 저장
            "year":       year,
            "debt_ratio": debt_ratio,
            **financials,
        },
        "embedding": embedding,
    }
    get_client().table("dart_rag_documents").upsert(row, on_conflict="chunk_id").execute()


def get_financial(corp_name: str, year: int) -> dict:

    # 기업 코드 조회
    corp = lookup_corp_code(corp_name)
    if not corp:
        raise ValueError(f"'{corp_name}' 기업을 찾을 수 없습니다.")

    corp_code        = corp["corp_code"]
    corp_name_official = corp["corp_name"]
    stock_code       = corp.get("stock_code")
    chunk_id         = f"{corp_code}_{year}"

    # 재무제표: DB 캐시 확인
    cached = (
        get_client()
        .table("dart_rag_documents")
        .select("metadata")
        .eq("chunk_id", chunk_id)
        .execute()
    )
    if cached.data:
        financials = dict(cached.data[0]["metadata"])
        source = "cache"
    else:
        # DART API 수집
        raw = fetch_financial_from_dart(corp_code, year)
        if raw is None:
            # 비상장사·미공시 — 재무데이터 없이 주가만 반환
            all_keys = {"revenue", "operating_profit", "net_income",
                        "total_assets", "total_liabilities", "total_equity", "debt_ratio"}
            financials = {k: None for k in all_keys}
            source = "no_data"
        else:
            financials = raw
            save_financial(corp_code, corp_name_official, stock_code, year, financials)
            source = "dart_api"

    # debt_ratio 계산 (캐시에 없거나 새로 수집한 경우 모두 보정)
    tl = financials.get("total_liabilities")
    te = financials.get("total_equity")
    if financials.get("debt_ratio") is None and tl and te and te != 0:
        financials["debt_ratio"] = round(tl / te * 100, 1)

    # 주가: 항상 실시간 조회 (매일 변동)
    market = get_market_data(stock_code) if stock_code else {"listed": False,
              "close": None, "market_cap": None, "high_52w": None, "low_52w": None}

    return {
        "corp_name":  corp_name_official,
        "stock_code": stock_code,
        "year":       year,
        "source":     source,
        **financials,
        **market,
    }