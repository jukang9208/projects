from fastapi import APIRouter, HTTPException
from schemas.classify import (
    IngestRequest, IngestBatchRequest, IngestResponse,
    SearchRequest, SearchResponse,
)
from services.rag import ingest_document, ingest_batch, search_documents

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    try:
        ingest_document(
            chunk_id=req.chunk_id,
            doc_id=req.doc_id,
            content=req.content,
            title=req.title,
            section=req.section,
            metadata=req.metadata,
        )
        return IngestResponse(chunk_id=req.chunk_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/batch", response_model=list[IngestResponse])
async def ingest_batch_endpoint(req: IngestBatchRequest):
    try:
        results = ingest_batch([doc.model_dump() for doc in req.documents])
        return [IngestResponse(chunk_id=doc["chunk_id"]) for doc in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    try:
        hits = search_documents(
            query=req.query,
            match_count=req.match_count,
            company_code=req.company_code,
            report_type=req.report_type,
            period=req.period,
        )
        return SearchResponse(results=hits, count=len(hits))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
