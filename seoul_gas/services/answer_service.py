from typing import Any
from services.answer_utils import to_python_type
from services.db_service import search_rag_documents
from services.question_service import parse_question
from services.answer_handlers.seoul_handler import answer_seoul_summary
from services.answer_handlers.comparison_handler import answer_comparison
from services.answer_handlers.trend_handler import answer_trend
from services.answer_handlers.cluster_handler import (
    answer_cluster,
    answer_general_cluster_question,
)
GENERAL_CLUSTER_KEYWORDS = ["속한", "목록", "어디", "어느"]
TREND_KEYWORDS = ["수급", "가스수급", "수급가구수", "소득", "인구", "가구", "변화", "추이", "현황"]

def _build_cluster_kpi(cluster_summary: dict | None) :
    if not cluster_summary :
        return None
    
    return [
        {
            "key": "population_avg",
            "label": "평균 인구",
            "value": cluster_summary.get("population_avg"),
            "unit": "명",
        },
        {
            "key": "households_avg",
            "label": "평균 가구수",
            "value": cluster_summary.get("households_avg"),
            "unit": "가구",
        },
        {
            "key": "gas_supply_avg",   
            "label": "평균 수급가구수", 
            "value": cluster_summary.get("gas_supply_avg"),       
            "unit": "가구", 
        },
        {
            "key": "income_avg",
            "label": "평균 소득",
            "value": cluster_summary.get("income_avg"),
            "unit": "원",
        },
        {
            "key": "gas_per_household_avg",
            "label": "가구당 수급",
            "value": cluster_summary.get("gas_per_household_avg"),
            "unit": "",
        }
    ]

def _detect_query_type(question: str, parsed: dict[str, Any]) -> str:
    districts = parsed.get("districts", [])
    target_cid = parsed.get("cluster_id")

    if "서울" in question and not districts:
        return "overview"

    if len(districts) >= 2:
        return "compare"

    if target_cid is not None and any(k in question for k in GENERAL_CLUSTER_KEYWORDS):
        return "cluster_list"

    if len(districts) == 1:
        if any(k in question for k in TREND_KEYWORDS):
            return "trend"
        return "cluster"

    return "general"

def _normalize_sources(raw_sources: Any) -> list[dict[str, Any]]:
    if not raw_sources:
        return []

    normalized = []
    for src in raw_sources:
        if not isinstance(src, dict):
            continue

        normalized.append({
            "type": src.get("type", "rag"),
            "section": src.get("section"),
            "chunk_id": src.get("chunk_id") or src.get("id"),
            "title": src.get("title"),
        })

    return normalized

def _extract_summary(result: dict[str, Any], default: str = "질문에 대한 분석 결과를 생성했습니다.") -> str:
    return (
        result.get("summary")
        or result.get("answer")
        or default
    )

def _build_response(
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

def _normalize_series(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [
        {
            "year": row["year"],
            "value": row.get(key),
        }
        for row in rows
        if row.get("year") is not None
    ]

def _normalize_trend_payload(raw: dict[str, Any]) -> dict[str, Any]:
    trend_raw = raw.get("trend") or raw.get("data") or {}
    rows = trend_raw.get("data", [])

    if not isinstance(rows, list):
        rows = []

    series = []

    total_pop_series = _normalize_series(rows, "total_pop")
    if total_pop_series:
        series.append({
            "key": "total_pop",
            "label": "총인구",
            "unit": "명",
            "data": total_pop_series,
        })

    gas_supply_series = _normalize_series(rows, "gas_supply")
    if gas_supply_series:
        series.append({
            "key": "gas_supply",
            "label": "가스 수급가구수",
            "unit": "가구",
            "data": gas_supply_series,
        })

    total_households_series = _normalize_series(rows, "total_households")
    if total_households_series:
        series.append({
            "key": "total_households",
            "label": "총가구수",
            "unit": "가구",
            "data": total_households_series,
        })

    avg_income_series = _normalize_series(rows, "avg_income")
    if avg_income_series:
        series.append({
            "key": "avg_income",
            "label": "평균소득",
            "unit": "원",
            "data": avg_income_series,
        })

    return {
        "district": trend_raw.get("district"),
        "type": trend_raw.get("type"),
        "label": trend_raw.get("label"),
        "series": series,
        "insights": raw.get("insights", []),
    }

def _normalize_cluster_payload(raw: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
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

def _normalize_cluster_list_payload(raw: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    items = raw.get("data") or raw.get("districts") or raw.get("items") or []
    if not isinstance(items, list):
        items = []

    return {
        "cluster_id": parsed.get("cluster_id"),
        "items": items,
        "insights": raw.get("insights", []),
    }

def _normalize_comparison_payload(raw: dict[str, Any]) -> dict[str, Any]:
    comparison_data = raw.get("comparison") or raw.get("data") or {}

    if not isinstance(comparison_data, dict):
        comparison_data = {"value": comparison_data}

    target = comparison_data.get("target")
    benchmark = comparison_data.get("benchmark")

    if target is None or benchmark is None:
        return {
            "data": comparison_data,
            "insights": raw.get("insights", []),
        }

    return {
        "target": target,
        "benchmark": benchmark,
        "insights": raw.get("insights", []),
    }

def _normalize_overview_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": _extract_summary(raw, default="서울 전체 요약 정보를 생성했습니다."),
        "data": raw.get("data"),
        "insights": raw.get("insights", []),
    }

def _normalize_rag_payload(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "documents": docs,
        "contents": [d.get("content") for d in docs if isinstance(d, dict) and d.get("content")],
    }

def answer_question(question: str) -> dict[str, Any]:
    try:
        parsed = parse_question(question)
        districts = parsed.get("districts", [])
        target_cid = parsed.get("cluster_id")
        query_type = _detect_query_type(question, parsed)

        if query_type == "overview":
            raw = to_python_type(answer_seoul_summary(parsed))
            return _build_response(
                question=question,
                query_type="overview",
                parsed=parsed,
                summary=_extract_summary(raw, default="서울 전체 요약 정보를 생성했습니다."),
                sections={
                    "overview": _normalize_overview_payload(raw),
                    "kpi": raw.get("kpi"),
                    "trend": raw.get("trend"),
                    "cluster": raw.get("cluster"),
                    "comparison": raw.get("comparison"),
                    "correlation": raw.get("correlation"),
                    "map": raw.get("map"),
                },
                sources=_normalize_sources(raw.get("sources", [])),
            )

        if query_type == "trend" and len(districts) == 1:
            parsed["district"] = districts[0]
            raw = to_python_type(answer_trend(parsed))

            return _build_response(
                question=question,
                query_type="trend",
                parsed=parsed,
                summary=_extract_summary(raw, default="시계열 분석 결과를 생성했습니다."),
                sections={
                    "trend": _normalize_trend_payload(raw),
                    "kpi": raw.get("kpi"),
                    "cluster": raw.get("cluster"),
                    "comparison": raw.get("comparison"),
                    "map": raw.get("map"),
                },
                sources=_normalize_sources(raw.get("sources", [])),
            )

        if query_type == "cluster" and len(districts) == 1:
            parsed["district"] = districts[0]
            raw = to_python_type(answer_cluster(parsed))

            return _build_response(
                question=question,
                query_type="cluster",
                parsed=parsed,
                summary=_extract_summary(raw, default="군집 분석 결과를 생성했습니다."),
                sections={
                    "cluster": _normalize_cluster_payload(raw, parsed),
                    "trend": raw.get("trend"),
                    "kpi": raw.get("kpi"),
                    "comparison": raw.get("comparison"),
                    "map": raw.get("map"),
                },
                sources=_normalize_sources(raw.get("sources", [])),
            )

        if query_type == "compare" and len(districts) >= 2:
            raw = to_python_type(answer_comparison(parsed))

            return _build_response(
                question=question,
                query_type="compare",
                parsed=parsed,
                summary=_extract_summary(raw, default="비교 분석 결과를 생성했습니다."),
                sections={
                    "comparison": _normalize_comparison_payload(raw),
                    "trend": raw.get("trend"),
                    "kpi": raw.get("kpi"),
                },
                sources=_normalize_sources(raw.get("sources", [])),
            )

        if query_type == "cluster_list" and target_cid is not None:
            raw = to_python_type(answer_general_cluster_question(parsed, target_cid))
            
            cluster_id = target_cid
            districts = raw.get("districts") or raw.get("items") or []
            cluster_summary = raw.get("cluster_summary")
            
            year = parsed.get("year")
            kpi_section = _build_cluster_kpi(cluster_summary)
            title = f"{year}, Cluster {cluster_id} 지도" if year else f"Cluster {cluster_id} 지도"

            map_section = {
                "title": title,
                "cluster_id": cluster_id,
                "districts": districts,
            }

            return _build_response(
                question=question,
                query_type="cluster_list",
                parsed=parsed,
                summary=_extract_summary(raw, default="군집 목록 정보를 생성했습니다."),
                sections={
                    "cluster_list": _normalize_cluster_list_payload(raw, parsed),
                    "map" : map_section,
                    "kpi": kpi_section,
                },
                sources=_normalize_sources(raw.get("sources", [])),
            )

        docs = to_python_type(search_rag_documents(question, match_count=3))

        return _build_response(
            question=question,
            query_type="general",
            parsed=parsed,
            summary="RAG 문서 기준으로 관련 내용을 찾았습니다." if docs else "질문에 해당하는 분석 결과를 찾지 못했습니다.",
            sections={
                "rag": _normalize_rag_payload(docs),
            },
            sources=_normalize_sources(docs),
        )

    except Exception as e:
        return {
            "question": question,
            "query_type": "error",
            "district": None,
            "year": None,
            "summary": f"분석 중 오류 발생: {str(e)}",
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
            },
            "sources": [],
        }