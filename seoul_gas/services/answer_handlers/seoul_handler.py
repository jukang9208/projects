from typing import Any
from services.db_service import analysis_service, search_rag_documents
from services.answer_utils import (
    format_number,
    get_metric_label,
    get_metric_unit,
)

def answer_seoul_summary(parsed: dict) -> dict[str, Any]:
    year = parsed.get("year") or 2024
    metric = parsed.get("metric", "gas_supply")
    label = get_metric_label(metric)
    unit = get_metric_unit(metric)

    df = analysis_service.get_merged_data(year)
    if df is None or df.empty:
        return {
            "intent": "seoul_summary",
            "district": "서울 전체",
            "year": year,
            "answer": f"{year}년 서울시 전체 데이터를 불러올 수 없습니다.",
            "stats": None,
            "sources": [],
        }

    if metric not in df.columns:
        return {
            "intent": "seoul_summary",
            "district": "서울 전체",
            "year": year,
            "answer": f"{year}년 서울시 전체 데이터에 '{metric}' 지표가 없습니다.",
            "stats": None,
            "sources": [],
        }

    total_val = df[metric].sum()
    avg_val = df[metric].mean()

    db_fact = (
        f"DB 분석 결과, {year}년 서울시 전체 {label} 합계는 약 "
        f"{format_number(total_val, unit)}이며, 자치구별 평균은 "
        f"{format_number(avg_val, unit)}이다."
    )

    docs = search_rag_documents(
        f"서울시 전체 {label} 현황 가스 수급 구조 해석",
        match_count=3,
    )

    rag_texts = [d.get("content", "").strip() for d in docs if d.get("content")]
    rag_combined = " ".join(rag_texts).strip()

    answer = db_fact
    if rag_combined:
        answer = f"{db_fact} {rag_combined}"

    return {
        "intent": "seoul_summary",
        "district": "서울 전체",
        "year": year,
        "answer": answer,
        "stats": {
            "total": total_val,
            "average": avg_val,
            "metric": metric,
            "label": label,
            "unit": unit,
        },
        "sources": docs,
    }