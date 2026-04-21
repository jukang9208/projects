from typing import Any
from services.db_service import seararch_rag_documents, get_district_trind
from services.answer_utils import (
    build_kpi,
    format_ratio,
    get_safe_val,
    format_number,
    get_metric_unit,
    get_metric_label,
)
from services.answer_handlers.llm_client import call_llm, filter_rag

_RATIO_METRICS = {"gas_supply_ratio", "home_ratio", "public_ratio", "service_ratio", "industry_ratio"}
_USAGE_KEYS    = ["home_usage", "public_usage", "service_usage", "industry_usage"]
_ALL_SERIES    = [
    ("home_usage",    "가정용",    "MWh"),
    ("public_usage",  "공공용",    "MWh"),
    ("service_usage", "서비스업",  "MWh"),
    ("industry_usage","산업용",    "MWh"),
]

_TREND_PROMPT = """당신은 서울시 에너지 데이터 분석 전문가입니다.
아래 [DB 수치]와 [보고서 참고]를 바탕으로 해당 자치구의 에너지 추세를 3~4문장으로 분석하세요.

규칙:
- 연도별 변화 수치를 구체적으로 인용
- 상주인구 변화와 에너지 소비 변화의 관계를 해석
- 보고서 내용은 {district} 관련 내용만 활용
- 다른 자치구 이름은 언급하지 말 것
- 한국어, 존댓말 금지, 요약문만 출력

[DB 수치]
{db_fact}

[보고서 참고]
{rag_text}
"""


def _get_metric_val(row: dict, metric: str) -> float:
    if metric == "total_usage":
        return sum(get_safe_val(row, k) for k in _USAGE_KEYS)
    return get_safe_val(row, metric)


def get_trend_type(start: dict, end: dict, metric: str) -> str:
    pop_diff    = get_safe_val(end, "total_resident_population") - get_safe_val(start, "total_resident_population")
    metric_diff = _get_metric_val(end, metric) - _get_metric_val(start, metric)

    if metric == "total_resident_population":
        if pop_diff > 0: return "인구 증가"
        if pop_diff < 0: return "인구 감소"
        return "인구 정체"

    if pop_diff < 0 and metric_diff > 0: return "인구 감소와 사용량 증가"
    if pop_diff > 0 and metric_diff < 0: return "인구 증가와 사용량 감소"
    if pop_diff < 0 and metric_diff < 0: return "동반 감소"
    if pop_diff > 0 and metric_diff > 0: return "동반 증가"
    return "정체"


def _build_db_fact(district: str, metric: str, label: str, unit: str,
                   trend_list: list[dict]) -> str:
    is_ratio = metric in _RATIO_METRICS
    start, end = trend_list[0], trend_list[-1]
    s_val = _get_metric_val(start, metric)
    e_val = _get_metric_val(end, metric)
    diff_pct = (e_val - s_val) / s_val * 100 if s_val != 0 else 0
    status   = "증가" if diff_pct > 0 else "감소" if diff_pct < 0 else "유지"

    fmt = format_ratio if is_ratio else lambda v, u="": format_number(v, u)

    yearly = []
    for row in trend_list:
        total = sum(get_safe_val(row, k) for k in _USAGE_KEYS)
        pop   = get_safe_val(row, "total_resident_population")
        val   = _get_metric_val(row, metric)
        yearly.append(
            f"  {row['year']}년: 전체 {format_number(total, 'MWh')}, "
            f"{label} {fmt(val, unit) if not is_ratio else fmt(val)}, "
            f"인구 {format_number(pop, '명')}"
        )

    return (
        f"{district} {label} 추세 ({start['year']}→{end['year']}):\n"
        f"  {start['year']}년 {fmt(s_val, unit) if not is_ratio else fmt(s_val)} → "
        f"{end['year']}년 {fmt(e_val, unit) if not is_ratio else fmt(e_val)} "
        f"({abs(diff_pct):.1f}% {status})\n"
        "연도별 상세:\n" + "\n".join(yearly)
    )


def answer_trend(parsed: dict) -> dict[str, Any]:
    district = parsed.get("district")
    metric   = parsed.get("metric", "total_usage")
    label    = get_metric_label(metric)
    unit     = get_metric_unit(metric)

    trend_list = get_district_trind(district)
    if not trend_list:
        return {"answer": f"{district}의 데이터를 찾을 수 없습니다.", "sources": []}

    trend_list = sorted(trend_list, key=lambda x: x.get("year", 0))
    start, end = trend_list[0], trend_list[-1]
    trend_type = get_trend_type(start, end, metric)

    db_fact = _build_db_fact(district, metric, label, unit, trend_list)

    docs = seararch_rag_documents(
        f"{district} {label} 변화 추세 에너지 소비 특성",
        match_count=5,
    )
    rag_text = filter_rag(docs, district)

    prompt  = _TREND_PROMPT.format(db_fact=db_fact, rag_text=rag_text, district=district)
    summary = call_llm(prompt, fallback=db_fact, handler_name="trend_handler")

    total_series = {
        "key": "total_usage", "label": "전체 전력사용량", "unit": "MWh",
        "data": [
            {"year": r["year"], "value": round(sum(get_safe_val(r, k) for k in _USAGE_KEYS))}
            for r in trend_list
        ],
    }
    usage_series = [
        {
            "key": key, "label": lbl, "unit": u,
            "data": [{"year": r["year"], "value": round(get_safe_val(r, key))} for r in trend_list],
        }
        for key, lbl, u in _ALL_SERIES
    ]
    pop_series = {
        "key": "total_resident_population", "label": "총상주인구", "unit": "명",
        "data": [{"year": r["year"], "value": round(get_safe_val(r, "total_resident_population"))} for r in trend_list],
    }

    return {
        "intent":   "trend",
        "district": district,
        "year":     parsed.get("year"),
        "answer":   summary,
        "kpi":      build_kpi(end),
        "trend": {
            "district": district,
            "type":     trend_type,
            "label":    label,
            "unit":     unit,
            "series":   [total_series] + usage_series + [pop_series],
            "data":     trend_list,
        },
        "sources": docs,
    }
