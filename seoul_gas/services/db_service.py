from google import genai  
from core.config import supabase, GOOGLE_API_KEY
from services.analysis_service import EnergyAnalysisService

analysis_service = EnergyAnalysisService(supabase)
client = genai.Client(api_key=GOOGLE_API_KEY)

EMBEDDING_MODEL = "models/gemini-embedding-001"

def get_latest_district_stats(district: str): 
    return analysis_service.get_latest_district_stats(district)

def get_district_trend(district: str): 
    return analysis_service.get_district_trend(district)

def get_latest_year_for_district(district: str):
    res = supabase.table("gas_supply").select("year").eq("district", district).order("year", desc=True).limit(1).execute()
    return res.data[0]["year"] if res.data else None

def get_district_cluster(year: int, district: str):
    df = analysis_service.get_merged_data(year)
    if df is None: 
        return None
        
    res = analysis_service.perform_clustering(df)
    row = res["data"][res["data"]["district"] == district]
    if row.empty: 
        return None
    
    cid = int(row.iloc[0]["cluster"])
    c_df = res["data"][res["data"]["cluster"] == cid]
    
    return {
        "year": year, 
        "district": district, 
        "cluster_id": cid,
        "cluster_summary": {
            "avg_gas_supply": c_df["gas_supply"].mean(), 
            "avg_income": c_df["avg_income"].mean()
        },
        "district_summary": row.iloc[0].to_dict()
    }

def search_rag_documents(query: str, match_count: int = 5) -> list[dict]:
    try:
        normalized_query = (query or "").strip()
        if not normalized_query: 
            return []

        #  Gemini API를 이용한 임베딩 생성 
        embedding_response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=normalized_query,
            config={
                "task_type": "retrieval_query", 
                "output_dimensionality": 768
            }
        )
        
        if not embedding_response or not embedding_response.embeddings: 
            return []
            
        query_embedding = embedding_response.embeddings[0].values
        
        # Supabase RPC 호출 파라미터 구성
        # filter_cluster_id는 DB 스키마에 따라 유동적이므로 기본 검색에서는 제외하여 범용성을 높임
        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": match_count, 
            "match_threshold": 0.3  # 유사도 30% 이상의 결과만 반환
        }
        
        print(f"[DEBUG] RAG Query: {normalized_query}")
        
        # RPC 호출 실행
        response = supabase.rpc("match_documents", rpc_params).execute()
        raw_data = response.data or []

        print(f"[DEBUG] RPC Returned Row Count: {len(raw_data)}")

        # 결과 데이터 클리닝 및 매핑
        cleaned_results = []
        for row in raw_data:
            
            cleaned_results.append({
                "id": row.get("chunk_id", "N/A"),           # 필수 필드: id (chunk_id 활용)
                "chunk_id": row.get("chunk_id", "N/A"),
                "doc_id": "seoul_gas_v1", 
                "section": row.get("section", "General"),
                "title": row.get("title", "분석 지표"),   
                "content": row.get("content", ""), 
                "metadata": {},                             # 필수 필드: metadata (빈 딕셔너리 추가)
                "similarity": float(row["similarity"]) if row.get("similarity") is not None else 0.0,
            })
            
        return cleaned_results

    except Exception as e:
        print(f"RAG search error in db_service: {repr(e)}")
        return []