from typing import Any
from services.db_service import analysis_service, search_rag_documents
from services.answer_utils import (
    format_number,
    get_metric_label,
    get_metric_unit,
)

def answer_comparison(parsed: dict) -> dict[str, Any]:
    districts = parsed.get("districts", [])
    metric = parsed.get("metric", "gas_supply")
    label = get_metric_label(metric)
    year = parsed.get("year") or 2024
    unit = get_metric_unit(metric)

    comp_results = []
    df = analysis_service.get_merged_data(year)

    if df is None or df.empty:
        return {"answer": "비교할 데이터가 없습니다.", "sources": []}

    if metric not in df.columns:
        return {
            "answer": f"{year}년 비교 데이터에 '{metric}' 지표가 없다.",
            "sources": [],
        }

    for dist in districts[:2]:
        row = df[df["district"] == dist]
        if not row.empty:
            val = float(row.iloc[0][metric])
            comp_results.append({"district": dist, "value": val})

    if len(comp_results) < 2:
        return {
            "answer": "비교 대상 자치구의 데이터를 모두 찾을 수 없습니다.",
            "sources": [],
        }

    d1, d2 = comp_results[0], comp_results[1]
    diff = abs(d1["value"] - d2["value"])
    higher = d1 if d1["value"] > d2["value"] else d2
    lower = d1 if d1["value"] < d2["value"] else d2

    db_fact = (
        f"DB 분석 결과, {year}년 {label}은 "
        f"{higher['district']}({format_number(higher['value'], unit)})가 "
        f"{lower['district']}({format_number(lower['value'], unit)})보다 "
        f"약 {format_number(diff, unit)} 더 많다."
    )

    docs = search_rag_documents(
        f"{d1['district']} {d2['district']} {label} 차이 해석 가스 수급 구조 비교",
        match_count=3,
    )
    rag_combined = " ".join([d["content"] for d in docs]) if docs else ""

    return {
        "intent": "comparison",
        "answer": f"{db_fact} {rag_combined}".strip(),
        "comparison": {
            "metric": metric,
            "items": comp_results,
            "year": year,
        },
        "sources": docs,
    }