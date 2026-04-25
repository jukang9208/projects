from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY
from services.embedder import embed_text, embed_query

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def ingest_document(
    chunk_id: str,
    doc_id: str,
    content: str,
    title: str | None = None,
    section: str | None = None,
    metadata: dict | None = None,
) -> dict:

    embedding = embed_text(content)

    row = {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "content": content,
        "title": title,
        "section": section,
        "metadata": metadata or {},
        "embedding": embedding,
    }

    result = (
        get_client()
        .table("dart_rag_documents")
        .upsert(row, on_conflict="chunk_id")
        .execute()
    )
    return result.data[0] if result.data else {}


def ingest_batch(documents: list[dict]) -> list[dict]:

    return [ingest_document(**doc) for doc in documents]

def search_documents(
    query: str,
    match_count: int = 5,
    company_code: str | None = None,
    report_type: str | None = None,
    period: str | None = None,
) -> list[dict]:

    query_embedding = embed_query(query)

    result = get_client().rpc(
        "match_dart_documents",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "filter_company_code": company_code,
            "filter_report_type": report_type,
            "filter_period": period,
        },
    ).execute()

    return result.data or []