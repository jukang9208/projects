from typing import Any
from services.answer_utils import to_python_type
from services.question_service import parse_question
from services.db_service import search_rag_documents
from services.answer_handlers.trend_handler import answer_trend
from services.answer_handlers.seoul_handler import answer_seoul_summary
from services.answer_handlers.comparison_handler import answer_comparison
from services.answer_handlers.cluster_handler import (
    answer_cluster, answwer_general_cluster_question) 
from services.answer_handlers.general_handler import answer_general
from services.answer_handlers.normalizers import (
    extract_summary,
    build_response, build_cluster_kpi,
    normalize_sources,
    normalize_trend_payload,
    normalize_cluster_payload,
    normalize_cluster_list_payload,
    normalize_comparison_payload,
    normalize_overview_payload,
    normalize_rag_payload,
)

GENERAL_CLUSTER_KEYWORDS = ["속한", "목록", "어디", "어느"]
TREND_KEYWORDS = ["수급", "가스", "전력", "전기", "소비", "인구", "가구", "변화", "추이", "현황", "보급", "비율"]

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

def answer_question(question: str) -> dict[str, Any]:
    try:
        parsed = parse_question(question)
        districts = parsed.get("districts", [])
        target_cid = parsed.get("cluster_id")
        query_type = _detect_query_type(question, parsed)

        if query_type == "overview":
            raw = to_python_type(answer_seoul_summary(parsed))
            rag_docs = raw.get("rag_docs") or raw.get("sources") or []
            return build_response(
                question = question,
                query_type = "overview",
                parsed = parsed,
                summary = extract_summary(raw, default="서울 전체 요약 정보를 생성했습니다."),
                sections = {
                    "overview": normalize_overview_payload(raw),
                    "kpi": raw.get("kpi"),
                    "trend": raw.get("trend"),
                    "cluster": raw.get("cluster"),
                    "comparison": raw.get("comparison"),
                    "correlation": raw.get("correlation"),
                    "map": raw.get("map"),
                    "rag": normalize_rag_payload(rag_docs),
                },
                sources = normalize_sources(raw.get("sources", [])),
            )
        if query_type == "trend":
            parsed["district"] = districts[0]
            raw = to_python_type(answer_trend(parsed))
            return build_response(
                question = question,
                query_type = "trend",
                parsed = parsed,
                summary = extract_summary(raw, default="시계열 분석 결과를 생성했습니다."),
                sections = {
                    "trend": normalize_trend_payload(raw),
                    "kpi": raw.get("kpi"),
                    "cluster": raw.get("cluster"),
                    "comparison": raw.get("comparison"),
                    "map": raw.get("map"),
                },
                sources = normalize_sources(raw.get("sources", [])),
            )

        if query_type == "cluster":
            parsed["district"] = districts[0]
            raw = to_python_type(answer_cluster(parsed))
            return build_response(
                question = question,
                query_type = "cluster",
                parsed = parsed,
                summary = extract_summary(raw, default="군집 분석 결과를 생성했습니다."),
                sections = {
                    "cluster": normalize_cluster_payload(raw, parsed),
                    "trend": raw.get("trend"),
                    "kpi": raw.get("kpi"),
                    "comparison": raw.get("comparison"),
                    "map": raw.get("map"),
                },
                sources=normalize_sources(raw.get("sources", [])),
            )

        if query_type == "compare":
            raw = to_python_type(answer_comparison(parsed))
            return build_response(
                question = question,
                query_type = "compare",
                parsed = parsed,
                summary = extract_summary(raw, default="비교 분석 결과를 생성했습니다."),
                sections = {
                    "comparison": normalize_comparison_payload(raw),
                    "trend": raw.get("trend"),
                    "kpi": raw.get("kpi"),
                },
                sources = normalize_sources(raw.get("sources", [])),
            )

        if query_type == "cluster_list":
            raw = to_python_type(answwer_general_cluster_question(parsed, target_cid))
            cluster_summary = raw.get("cluster_summary")
            year = parsed.get("year")
            title = f"{year}, Cluster {target_cid} 지도" if year else f"Cluster {target_cid} 지도"
            return build_response(
                question = question,
                query_type = "cluster_list",
                parsed = parsed,
                summary = extract_summary(raw, default="군집 목록 정보를 생성했습니다."),
                sections={
                    "cluster_list": normalize_cluster_list_payload(raw, parsed),
                    "map": {
                        "title": title,
                        "cluster_id": target_cid,
                        "districts": raw.get("districts") or raw.get("items") or [],
                    },
                    "kpi": build_cluster_kpi(cluster_summary),
                },
                sources=normalize_sources(raw.get("sources", [])),
            )
        raw = answer_general(question)
        return build_response(
            question = question,
            query_type = "general",
            parsed = parsed,
            summary = extract_summary(raw, default="질문에 대한 분석 결과를 생성했습니다."),
            sections = {
                "rag": normalize_rag_payload(raw["docs"]),
            },
            sources = normalize_sources(raw["sources"]),
        )
    except Exception as e:
        return {
            "question": question,
            "query_type": "error",
            "district": None,
            "year": None,
            "summary": f"분석 중 오류 발생: {str(e)}",
            "sections": {
                "kpi": None, "trend": None, "cluster": None,
                "comparison": None, "correlation": None, "map": None,
                "overview": None, "rag": None, "cluster_list": None,
            },
            "sources": [],
        }
