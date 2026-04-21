-- =====================================================================
-- rag.sql
-- seoul_energy_rag 프로젝트 RAG(벡터 검색) 스키마
-- pgvector 확장 + energy_rag_documents 테이블 + match_documents 함수
-- =====================================================================

-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- RAG 테이블 생성
CREATE TABLE IF NOT EXISTS public.energy_rag_documents (
    id bigserial PRIMARY KEY,
    chunk_id text NOT NULL UNIQUE,
    doc_id text NOT NULL,
    section text,
    title text,
    content text NOT NULL, -- 검색 결과로 노출될 본문
    metadata jsonb DEFAULT '{}'::jsonb, -- cluster_id, keywords 등 저장
    embedding vector(768),
    created_at timestamp DEFAULT now()
);

-- 인덱스 설정 (검색 속도 최적화)
-- 벡터 유사도 검색용 HNSW 인덱스
CREATE INDEX IF NOT EXISTS idx_energy_rag_documents_embedding
ON public.energy_rag_documents USING hnsw (embedding vector_cosine_ops);

-- 특정 필드 빠른 조회를 위한 B-Tree 인덱스
CREATE INDEX IF NOT EXISTS idx_energy_rag_documents_chunk_id ON public.energy_rag_documents(chunk_id);
-- 메타데이터 내 cluster_id 필터링 성능 향상
CREATE INDEX IF NOT EXISTS idx_energy_rag_documents_metadata_cluster_id
ON public.energy_rag_documents ((metadata->>'cluster_id'));
-- JSONB 전체 검색용 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_energy_rag_documents_metadata_gin ON public.energy_rag_documents USING gin (metadata);

-- RLS 설정
ALTER TABLE public.energy_rag_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow read" ON public.energy_rag_documents;
CREATE POLICY "Allow read" ON public.energy_rag_documents FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "Allow write" ON public.energy_rag_documents;
CREATE POLICY "Allow write" ON public.energy_rag_documents FOR ALL TO authenticated USING (true);

-- 벡터 검색 함수
-- filter_cluster_id를 넘기면 해당 클러스터만 검색하고, NULL이면 전체를 검색
CREATE OR REPLACE FUNCTION public.match_energy_documents(
    query_embedding vector(768),
    match_count int DEFAULT 5,
    filter_cluster_id text DEFAULT NULL
)
RETURNS TABLE (
    id bigint,
    chunk_id text,
    doc_id text,
    section text,
    title text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rd.id,
        rd.chunk_id,
        rd.doc_id,
        rd.section,
        rd.title,
        rd.content,
        rd.metadata,
        1 - (rd.embedding <=> query_embedding) AS similarity
    FROM public.energy_rag_documents rd
    WHERE
        rd.embedding IS NOT NULL
        AND (
            filter_cluster_id IS NULL
            OR rd.metadata->>'cluster_id' = filter_cluster_id
        )
    ORDER BY rd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
