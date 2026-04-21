from typing import Any
from services.answer_utils import (
    build_kpi,
    get_safe_val,
    format_number,
    get_cluster_label_from_profile,
)
from services.db_service import (
    get_district_stats,
    get_all_cluster_data,
    get_district_cluster,
    seararch_rag_documents,
)
from services.answer_handlers.llm_client import call_llm, clean_rag

K = 6

_CLUSTER_PROMPT = """당신은 서울시 에너지 데이터 분석 전문가입니다.
아래 [자치구 데이터]와 [분석 보고서 내용]을 바탕으로 해당 자치구의 에너지 소비 특성을 3~4문장으로 자연스럽게 설명하세요.

규칙:
- DB 수치를 우선 사용하고 보고서 인사이트를 보조적으로 활용
- 반드시 상주인구 수치를 포함할 것
- 군집 특성과 해당 자치구의 위치를 연결해 해석
- 차트 눈금, 반복 문장, 목록 나열은 제거
- 한국어로 작성, 존댓말 사용 금지
- 요약문만 출력 (제목, 마크다운 불필요)

[자치구 데이터]
{db_fact}

[분석 보고서 내용]
{rag_text}
"""
_USAGE_KEYS = ["home_usage", "public_usage", "service_usage", "industry_usage"]


def _build_db_fact(district: str, year: int, cid: int, label: str,
                   stats: dict | None) -> str:
    base = f"{year}년 {district}는 Cluster {label}({cid})에 속한다."
    if not stats:
        return base
    home     = get_safe_val(stats, "home_usage")
    public   = get_safe_val(stats, "public_usage")
    service  = get_safe_val(stats, "service_usage")
    industry = get_safe_val(stats, "industry_usage")
    total    = home + public + service + industry
    pop      = get_safe_val(stats, "total_resident_population")
    home_r   = float(stats.get("home_ratio") or 0) * 100
    svc_r    = float(stats.get("service_ratio") or 0) * 100
    ind_r    = float(stats.get("industry_ratio") or 0) * 100
    return (
        f"{base} "
        f"전체 전력사용량 {format_number(total, 'MWh')}, "
        f"가정용 {format_number(home, 'MWh')}({home_r:.1f}%), "
        f"서비스업 {format_number(service, 'MWh')}({svc_r:.1f}%), "
        f"산업용 {format_number(industry, 'MWh')}({ind_r:.1f}%). "
        f"상주인구 {format_number(pop, '명')}."
    )


def answer_cluster(parsed: dict) -> dict[str, Any]:
    district = parsed.get("district")
    year     = parsed.get("year") or 2024

    cluster_data = get_district_cluster(year, district)
    if not cluster_data:
        return {"answer": "군집 정보가 없습니다.", "sources": []}

    cid   = cluster_data["cluster_id"]
    stats = get_district_stats(district, year)
    kpi   = build_kpi(stats)

    cluster_summary_data = cluster_data.get("cluster_summary") or {}
    label = get_cluster_label_from_profile(cluster_summary_data, cid)

    docs = seararch_rag_documents(
        f"{district} Cluster {label} {cid} 특징 에너지 소비 해석",
        match_count=3,
    )

    db_fact  = _build_db_fact(district, year, cid, label, stats)
    rag_text = clean_rag(docs)
    prompt   = _CLUSTER_PROMPT.format(db_fact=db_fact, rag_text=rag_text or "(보고서 내용 없음)")
    summary  = call_llm(prompt, fallback=db_fact, handler_name="cluster_handler")

    return {
        "intent":  "cluster",
        "answer":  summary,
        "cluster": {
            **cluster_data,
            "cluster_label": label,
        },
        "kpi":     kpi,
        "sources": docs,
    }


def answwer_general_cluster_question(parsed: dict, target_cid: int) -> dict[str, Any]:
    year = parsed.get("year") or 2024

    all_data = get_all_cluster_data(k=K)
    if all_data["status"] != "success":
        return {"answer": "데이터가 없습니다.", "sources": []}

    districts_data       = all_data["data"]["districts"]
    cluster_summary_list = all_data["data"]["cluster_summary"]

    year_records = [
        r for r in districts_data
        if r.get("year") == year and int(r.get("cluster", -1)) == target_cid
    ]
    districts    = list(dict.fromkeys([r["district"] for r in year_records]))
    cluster_info = next(
        (c for c in cluster_summary_list if c["cluster"] == target_cid), {}
    )
    mean_profile = cluster_info.get("mean_profile", {})

    def _avg(col):
        return round(mean_profile.get(col, 0), 4) if col in mean_profile else None

    cluster_summary = {
        "cluster_id":          target_cid,
        "population_avg":      _avg("total_resident_population"),
        "households_avg":      _avg("total_households"),
        "gas_supply_ratio_avg":_avg("gas_supply_ratio"),
        "home_ratio_avg":      _avg("home_ratio"),
        "service_ratio_avg":   _avg("service_ratio"),
        "industry_ratio_avg":  _avg("industry_ratio"),
    }

    label = get_cluster_label_from_profile(cluster_summary, target_cid)

    docs = seararch_rag_documents(
        f"Cluster {label} {target_cid} 특징 해석 정책 시사점",
        match_count=3,
    )
    district_text = ", ".join(districts) if districts else "해당 없음"
    db_fact  = f"{year}년 Cluster {label}({target_cid})에 속한 자치구: {district_text}."
    rag_text = clean_rag(docs)
    prompt   = _CLUSTER_PROMPT.format(db_fact=db_fact, rag_text=rag_text or "(보고서 내용 없음)")
    summary  = call_llm(prompt, fallback=db_fact, handler_name="cluster_handler")

    return {
        "intent": "general_cluster",
        "answer": summary,
        "cluster": {
            "cluster_id":    target_cid,
            "cluster_label": label,
            "districts":     districts,
            "year":          year,
        },
        "cluster_summary": cluster_summary,
        "districts":       districts,
        "sources":         docs,
    }
