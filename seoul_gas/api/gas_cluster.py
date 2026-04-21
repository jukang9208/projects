from fastapi import APIRouter
from core.config import supabase
from services.analysis_service import EnergyAnalysisService

router = APIRouter()

analysis_service = EnergyAnalysisService(supabase)


@router.get("/clusters/{year}")
def get_energy_clusters(year: int):
    df = analysis_service.get_merged_data(year)

    if df is None:
        return {"error": "해당 연도의 충분한 데이터가 없습니다."}

    elbow_raw = analysis_service.find_optimal_k(df, max_k=6)

    elbow_data = [
        {
            "k": k,
            "inertia": round(inertia, 2)
        }
        for k, inertia in zip(elbow_raw["k_range"], elbow_raw["inertias"])
    ]

    clustering_result = analysis_service.perform_clustering(df, n_clusters=4)
    result_df = clustering_result["data"]
    metrics = clustering_result["metrics"]

    return {
        "year": year,
        "count": len(result_df),
        "metrics": metrics,
        "elbow": elbow_data,
        "data": result_df.to_dict(orient="records")
    }