from sqlalchemy import text
from db.database import SessionLocal
from core.config import supabase, genai_client

EMBEDDING_MODEL = "models/gemini-embedding-001"

def _get_db() :

    return SessionLocal()

def get_district_trind(district : str) -> list:
    db = _get_db()
    try :
        query = text("""
            SELECT year, district, total_resident_population, total_households,
                     gas_supply, gas_supply_ratio,
                     home_usage, public_usage, service_usage, industry_usage,
                     home_ratio, public_ratio, service_ratio, industry_ratio
            FROM seoul_district_energy_stats
            WHERE district = :district
            ORDER BY year ASC
        """)
        result = db.execute(query, {"district" : district})
        return [dict(row._mapping) for row in result]
    finally :
        db.close()


def get_district_stats(district: str, year: int) -> dict | None:

    db = _get_db()
    try:
        query = text("""
            SELECT year, district, total_resident_population, total_households,
                   gas_supply, gas_supply_ratio,
                   home_usage, public_usage, service_usage, industry_usage,
                   home_ratio, public_ratio, service_ratio, industry_ratio
            FROM seoul_district_energy_stats
            WHERE district = :district AND year = :year
            LIMIT 1
        """)
        result = db.execute(query, {"district": district, "year": year})
        row = result.fetchone()
        return dict(row._mapping) if row else None
    finally:
        db.close()


def get_district_cluster(year: int, district: str) -> dict | None:
    db = _get_db()
    try:
        from services.analysis_service import get_kmeans_clusters
        result = get_kmeans_clusters(db, k=6)   
    finally:
        db.close()

    if result["status"] != 'success':
        return None
    
    districts_data = result["data"]["districts"]
    cluster_summary_list = result["data"]["cluster_summary"]

    record = next(
        (r for r in districts_data if r["district"] == district and r.get("year") == year),
        None,
    )
    if record is None:
        return None
    
    cid = int(record["cluster"])
    cluster_info = next((c for c in cluster_summary_list if c["cluster"] == cid), {})
    mean_profile = cluster_info.get("mean_profile", {})

    return {
        "year" : year,
        "district" : district,
        "cluster_id" : cid,
        "cluster_summary" : {
            "population_avg" : mean_profile.get("total_resident_population"),
            "households_avg" : mean_profile.get("total_households"),
            "gas_supply_ratio_avg" : mean_profile.get("gas_supply_ratio"),
            "home_ratio_avg" : mean_profile.get("home_ratio"),
            "service_ratio_avg" : mean_profile.get("service_ratio"),
            "industry_ratio_avg" : mean_profile.get("industry_ratio"),
        },
        "district_summary" : record,
    }

def get_all_cluster_data(k: int = 6) -> dict:   
    db = _get_db()
    try:
        from services.analysis_service import get_kmeans_clusters
        return get_kmeans_clusters(db, k=k)
    finally:
        db.close()

def seararch_rag_documents(query: str, match_count: int = 5) -> list[dict]:
    try:
        nomalized_query = (query or "").strip()
        if not nomalized_query:
            return []
        
        embedding_responce = genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents = nomalized_query,
            config={
                "task_type": "retrieval_query",
                "output_dimensionality" : 768,
            },
        )

        if not embedding_responce or not embedding_responce.embeddings:
            return[]
        
        query_embedding = embedding_responce.embeddings[0].values
        rpc_params = {
            "query_embedding" : query_embedding,
            "match_count" : match_count,
            "filter_cluster_id" : None,
        }
        print(f"[DEBUG] RAG Query: {nomalized_query}")

        response = supabase.rpc("match_energy_documents", rpc_params).execute()
        raw_data = response.data or []
        print(f"[DEBUG] RPC Returned Row Count : {len(raw_data)}")

        cleaned_results = []
        for row in raw_data:
            cleaned_results.append(
                {
                    "id" : row.get("chunk_id", "N/A"),
                    "chunk_id" : row.get("chunk_id", "N/A"),
                    "doc_id" : "seoul_energy_cluster_analysis_v2",
                    "section" : row.get("section", "General"),
                    "title" : row.get("title", "분석 지표"),
                    "content" : row.get("content", ""),
                    "metadata" : {},
                    "similarity" : float(row["similarity"]) if row.get("similarity") is not None else 0.0,
                }
            )
        return cleaned_results
        
    except Exception as e:
        print(f"RAG search error in db_service: {repr(e)}")
        return []