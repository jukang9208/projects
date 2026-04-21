import os
import json
from google import genai
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("supabase_URL")
SUPABASE_KEY = os.getenv("supabase_KEY") 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)
EMBEDDING_MODEL = "models/gemini-embedding-001"

def get_gemini_embedding(text: str) -> list[float]:
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "task_type": "retrieval_document",
            "output_dimensionality": 768
        }
    )
    return response.embeddings[0].values

def upload_enriched_documents(file_path: str, batch_size: int = 10):
    if not os.path.exists(file_path):
        print(f"파일을 찾을 수 없습니다: {file_path}")
        return

    documents = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))

    print(f"총 {len(documents)}개의 청크 로드 완료. 임베딩 및 업로드 시작")
    
    payload_batch = []
    for i, doc in enumerate(documents):
        try:
            # 제목과 키워드를 본문과 결합하여 벡터 검색 정확도 향상
            keywords_str = ", ".join(doc.get("keywords", []))
            enriched_text = f"제목: {doc['title']}\n내용: {doc['text']}\n키워드: {keywords_str}"
            
            embedding_vector = get_gemini_embedding(enriched_text)
            
            # 메타데이터 정제 
            metadata = {"keywords": doc.get("keywords", [])}
            if "cluster_id" in doc:
                metadata["cluster_id"] = str(doc["cluster_id"])
            if "cluster_name" in doc:
                metadata["cluster_name"] = doc["cluster_name"]

            payload = {
                "chunk_id": doc["chunk_id"],
                "doc_id": doc["doc_id"],
                "section": doc["section"],
                "title": doc["title"],
                "content": doc["text"], # 답변용으로는 순수 텍스트만 저장
                "metadata": metadata,
                "embedding": embedding_vector
            }
            payload_batch.append(payload)

            # 배치 업로드
            if len(payload_batch) >= batch_size or i == len(documents) - 1:
                supabase.table("rag_documents").insert(payload_batch).execute()
                print(f"진행 완료: {i+1}/{len(documents)}")
                payload_batch = []
                
        except Exception as e:
            print(f"실패: {doc.get('chunk_id')} | 에러: {e}")

    print("모든 데이터 적재가 완료되었습니다.")

if __name__ == "__main__":
    
    FILE_PATH = os.path.join("data", "processed", "seoulgas_chunks.jsonl") 
    upload_enriched_documents(FILE_PATH)