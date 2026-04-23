from typing import Any
from sqlalchemy import text
from db.database import SessionLocal
from services.db_service import search_rag_documents
from services.answer_utils import format_number
from services.answer_handlers.llm_client import call_llm, filter_rag

_COMPARE_COLUMNS = [
    ("home_usage",               "가정용",     "MWh"),
    ("public_usage",             "공공용",     "MWh"),
    ("service_usage",            "서비스업",   "MWh"),
    ("industry_usage",           "산업용",     "MWh"),
    ("total_resident_population","총상주인구", "명"),
]

_COMPARE_PROMPT = """당신은 서울시 에너지 데이터 분석 전문가입니다.
아래 [DB 수치]와 [보고서 참고]를 바탕으로 두 자치구의 에너지 소비 구조 차이를 3~5문장으로 분석하세요.

규칙:
- DB 수치(전력량·비율·인구)를 구체적으로 인용
- 총상주인구 수치를 반드시 포함
- 두 자치구의 소비 구조 차이와 그 의미를 해석
- 보고서 내용은 보조 참고용이며 {d1}·{d2} 관련 내용만 활용
- 다른 자치구 이름은 절대 언급하지 말 것
- 한국어, 존댓말 금지, 요약문만 출력

[DB 수치]
{db_fact}

[보고서 참고]
{rag_text}
"""


def _calc_ratio(usage: float, total: float) -> float:
    return round(usage / total * 100, 1) if total > 0 else 0.0


def _build_db_fact(d1: str, d2: str, r1: dict, r2: dict, year: int) -> str:
    t1, t2 = r1["total_usage"], r2["total_usage"]

    def ratio_block(r: dict, name: str) -> str:
        t = r["total_usage"]
        return (
            f"{name}: 전체 {format_number(t, 'MWh')}, "
            f"가정용 {format_number(r['home_usage'], 'MWh')}({_calc_ratio(r['home_usage'], t)}%), "
            f"서비스업 {format_number(r['service_usage'], 'MWh')}({_calc_ratio(r['service_usage'], t)}%), "
            f"산업용 {format_number(r['industry_usage'], 'MWh')}({_calc_ratio(r['industry_usage'], t)}%), "
            f"공공용 {format_number(r['public_usage'], 'MWh')}({_calc_ratio(r['public_usage'], t)}%). "
            f"상주인구 {format_number(r['total_resident_population'], '명')}."
        )

    diff_t   = abs(t1 - t2)
    diff_pct = round(diff_t / min(t1, t2) * 100, 1) if min(t1, t2) > 0 else 0.0
    higher_t = d1 if t1 >= t2 else d2

    return (
        f"{year}년 기준.\n"
        f"{ratio_block(r1, d1)}\n"
        f"{ratio_block(r2, d2)}\n"
        f"전체 전력사용량은 {higher_t}가 더 높으며, 차이는 {format_number(diff_t, 'MWh')}({diff_pct}%)."
    )


def answer_comparison(parsed: dict) -> dict[str, Any]:
    districts = parsed.get("districts", [])
    year      = parsed.get("year") or 2024

    db = SessionLocal()
    try:
        query = text("""
            SELECT district,
                   home_usage, public_usage, service_usage, industry_usage,
                   total_resident_population
            FROM seoul_district_energy_stats
            WHERE year = :year AND district = ANY(:districts)
        """)
        result = db.execute(query, {"year": year, "districts": list(districts[:2])})
        rows = {
            row.district: {
                "home_usage":                float(row.home_usage or 0),
                "public_usage":              float(row.public_usage or 0),
                "service_usage":             float(row.service_usage or 0),
                "industry_usage":            float(row.industry_usage or 0),
                "total_resident_population": float(row.total_resident_population or 0),
            }
            for row in result
        }
    finally:
        db.close()

    if len([d for d in districts[:2] if d in rows]) < 2:
        return {"answer": "비교 대상 자치구의 데이터를 찾을 수 없습니다.", "sources": []}

    d1_name, d2_name = districts[0], districts[1]
    r1, r2 = rows[d1_name], rows[d2_name]

    usage_keys = ["home_usage", "public_usage", "service_usage", "industry_usage"]
    r1["total_usage"] = sum(r1[k] for k in usage_keys)
    r2["total_usage"] = sum(r2[k] for k in usage_keys)

    compare_items = []
    for col, lbl, unit in [("total_usage", "전체 전력사용량", "MWh")] + _COMPARE_COLUMNS:
        v1, v2 = r1[col], r2[col]
        higher = d1_name if v1 >= v2 else d2_name
        compare_items.append({
            "key":       col,
            "label":     lbl,
            "unit":      unit,
            d1_name:     round(v1),
            d2_name:     round(v2),
            "diff":      round(abs(v1 - v2)),
            "ratio_pct": round(abs((v1 - v2) / v2 * 100) if v2 != 0 else 0.0, 2),
            "higher":    higher,
        })

    db_fact = _build_db_fact(d1_name, d2_name, r1, r2, year)

    docs = search_rag_documents(
        f"{d1_name} {d2_name} 에너지 소비 구조 비교 군집 특성",
        match_count=3,
    )
    rag_text = filter_rag(docs, d1_name, d2_name)

    prompt  = _COMPARE_PROMPT.format(db_fact=db_fact, rag_text=rag_text, d1=d1_name, d2=d2_name)
    summary = call_llm(prompt, fallback=db_fact, handler_name="comparison_handler")

    return {
        "intent": "comparison",
        "answer": summary,
        "comparison": {
            "year":      year,
            "districts": [d1_name, d2_name],
            "items":     compare_items,
        },
        "sources": docs,
    }
