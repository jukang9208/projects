from typing import Any
from services.answer_utils import CLUSTER_LABELS
from services.db_service import (
    get_district_cluster,
    search_rag_documents,
    analysis_service,
)

def answer_cluster(parsed: dict) -> dict[str, Any]:
    district = parsed.get("district")
    year = parsed.get("year") or 2024

    cluster_data = get_district_cluster(year, district)
    if not cluster_data:
        return {"answer": "군집 정보가 없습니다.", "sources": []}

    cid = cluster_data["cluster_id"]
    label = CLUSTER_LABELS.get(cid, f"Cluster {cid}")

    docs = search_rag_documents(
        f"Cluster {cid} {label} 특징 해석 정책 시사점",
        match_count=3,
    )
    rag_combined = " ".join([d["content"] for d in docs]) if docs else ""

    db_fact = (
        f"DB 분석 결과, {year}년 {district}는 "
        f"Cluster {cid}({label})에 속한다."
    )

    return {
        "intent": "cluster",
        "answer": f"{db_fact} {rag_combined}".strip(),
        "cluster": {
            **cluster_data,
            "cluster_label": label,
        },
        "sources": docs,
    }

def answer_general_cluster_question(parsed: dict, target_cid: int) -> dict[str, Any]:
    year = parsed.get("year") or 2024
    all_data = analysis_service.get_merged_data(year)

    if all_data is None or all_data.empty:
        return {"answer": "데이터가 없습니다.", "sources": []}

    res = analysis_service.perform_clustering(all_data)
    cluster_df = res["data"]

    cluster_rows = cluster_df[cluster_df["cluster"] == target_cid]
    districts = cluster_df[cluster_df["cluster"] == target_cid]["district"].tolist()

    label = CLUSTER_LABELS.get(target_cid, f"Cluster {target_cid}")
    
    def avg(col):
        if col not in cluster_rows:
            return None
        return round(cluster_rows[col].mean(), 2)
    
    valid_rows = cluster_rows[
        (cluster_rows["gas_supply"].notna())
        & cluster_rows["total_households"].notna()
        & (cluster_rows["total_households"] > 0)
    ]

    income_avg = avg("avg_income")
    if income_avg and income_avg > 100000:
        income_avg = round(income_avg / 10000, 2)
    
    gas_per_household_avg = None
    if not valid_rows.empty:
        gas_per_household_avg = round(
            (valid_rows["gas_supply"] / valid_rows["total_households"]).mean(),2
        )
    
    cluster_summary = {
        "cluster_id": target_cid,
        "population_avg": avg("total_pop"),
        "households_avg": avg("total_households"),
        "gas_supply_avg": avg("gas_supply"),
        "income_avg": avg("avg_income"),
        "gas_per_household_avg": gas_per_household_avg,
    }

    docs = search_rag_documents(
        f"Cluster {target_cid} {label} 특징 해석 정책 시사점",
        match_count=3,
    )
    rag_combined = " ".join([d["content"] for d in docs]) if docs else ""

    district_text = ", ".join(districts) if districts else "해당 없음"

    return {
        "intent": "general_cluster",
        "answer": (
            f"{year}년 Cluster {target_cid}({label})에 속한 자치구는 "
            f"{district_text}이다. {rag_combined}"
        ).strip(),
        "cluster": {
            "cluster_id": target_cid,
            "cluster_label": label,
            "districts": districts,
            "year": year,
        },
        "cluster_summary": cluster_summary,
        "districts": districts,
        "sources": docs,
    }