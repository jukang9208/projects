from typing import Any

def extract_summary(result: dict[str, Any], default: str = "질문에 대한 분석 결과를 생성했습니다.") -> str:
    return result.get("summary") or result.get("answer") or default

def build_response(
    *,
    question: str,
    query_type: str,
    parsed: dict[str, Any],
    summary: str,
    sections: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    districts = parsed.get("districts", [])
    district = parsed.get("district") or (districts[0] if len(districts) == 1 else None)
    return {
        "question": question,
        "query_type": query_type,
        "district": district,
        "year": parsed.get("year"),
        "summary": summary,
        "sections": {
            "kpi": None,
            "trend": None,
            "cluster": None,
            "comparison": None,
            "correlation": None,
            "map": None,
            "overview": None,
            "rag": None,
            "cluster_list": None,
            **(sections or {}),
        },
        "sources": sources or [],
    }

def normalize_sources(raw_sources: Any) -> list[dict[str, Any]]:
    if not raw_sources:
        return []
    normalized = []
    for src in raw_sources:
        if not isinstance(src, dict):
            continue
        normalized.append(
            {
                "type": src.get("type", "rag"),
                "section": src.get("section"),
                "chunk_id": src.get("chunk_id") or src.get("id"),
                "title": src.get("title"),
            }
        )
    return normalized

def normalize_trend_payload(raw: dict[str, Any]) -> dict[str, Any]:
    trend_raw = raw.get("trend") or raw.get("data") or {}
    return {
        "district": trend_raw.get("district"),
        "type": trend_raw.get("type"),
        "label": trend_raw.get("label"),
        "unit": trend_raw.get("unit"),
        "series": trend_raw.get("series", []),
        "insights": raw.get("insights", []),
    }

def normalize_cluster_payload(raw: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    cluster_data = raw.get("cluster") or raw.get("data") or {}
    if not isinstance(cluster_data, dict):
        cluster_data = {"value": cluster_data}
    return {
        "district": parsed.get("district"),
        "cluster_id": cluster_data.get("cluster_id") or parsed.get("cluster_id"),
        "cluster_label": cluster_data.get("cluster_label") or cluster_data.get("label"),
        "description": (
            cluster_data.get("description")
            or cluster_data.get("answer")
            or raw.get("answer")
        ),
        "policy_insights": (
            cluster_data.get("policy_insights")
            or raw.get("policy_insights")
            or raw.get("insights", [])
        ),
        "data": cluster_data,
    }

def normalize_cluster_list_payload(raw: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    items = raw.get("data") or raw.get("districts") or raw.get("items") or []
    if not isinstance(items, list):
        items = []
    return {
        "cluster_id": parsed.get("cluster_id"),
        "items": items,
        "insights": raw.get("insights", []),
    }

def normalize_comparison_payload(raw: dict[str, Any]) -> dict[str, Any]:
    comparison_data = raw.get("comparison") or raw.get("data") or {}
    if not isinstance(comparison_data, dict):
        comparison_data = {"value": comparison_data}
    target = comparison_data.get("target")
    benchmark = comparison_data.get("benchmark")
    if target is None or benchmark is None:
        return {"data": comparison_data, "insights": raw.get("insights", [])}
    return {"target": target, "benchmark": benchmark, "insights": raw.get("insights", [])}

def normalize_overview_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": extract_summary(raw, default="서울 전체 요약 정보를 생성했습니다."),
        "data": raw.get("data"),
        "insights": raw.get("insights", []),
    }

def normalize_rag_payload(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "documents": docs,
        "contents": [d.get("content") for d in docs if isinstance(d, dict) and d.get("content")],
    }

def build_cluster_kpi(cluster_summary: dict | None) -> list | None:
    if not cluster_summary:
        return None
    return [
        {"key": "population_avg", "label": "평균 상주인구", "value": cluster_summary.get("population_avg"), "unit": "명"},
        {"key": "households_avg", "label": "평균 가구수", "value": cluster_summary.get("households_avg"), "unit": "가구"},
        {"key": "gas_supply_ratio_avg", "label": "평균 가스 보급률", "value": cluster_summary.get("gas_supply_ratio_avg"), "unit": ""},
        {"key": "home_ratio_avg", "label": "평균 가정용 전력 비율", "value": cluster_summary.get("home_ratio_avg"), "unit": ""},
        {"key": "service_ratio_avg", "label": "평균 서비스업 전력 비율", "value": cluster_summary.get("service_ratio_avg"), "unit": ""},
    ]