CREATE TABLE IF NOT EXISTS public.dart_rag_documents (
    id          bigserial   PRIMARY KEY,
    chunk_id    text        NOT NULL UNIQUE,          -- 청크 고유 ID (doc_id + chunk 순번 등)
    doc_id      text        NOT NULL,                  -- 원문 공시 문서 ID (DART rcept_no 등)
    section     text,                                  -- 문서 내 섹션명 (사업개요, 재무정보 등)
    title       text,                                  -- 공시 제목
    content     text        NOT NULL,                  -- 검색 결과로 노출될 본문
    metadata    jsonb       DEFAULT '{}'::jsonb,       -- company_code, report_type, period 등
    embedding   vector(768),                           -- Gemini text-embedding-004
    created_at  timestamp   DEFAULT now()
);
 
-- ── 인덱스 설정 ───────────────────────────────────────────────────────
 
-- 벡터 유사도 검색용 HNSW 인덱스
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_embedding
    ON public.dart_rag_documents USING hnsw (embedding vector_cosine_ops);
 
-- chunk_id 빠른 조회
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_chunk_id
    ON public.dart_rag_documents (chunk_id);
 
-- doc_id 기준 필터링 (특정 공시 문서 내 검색)
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_doc_id
    ON public.dart_rag_documents (doc_id);
 
-- metadata.company_code 필터링 (종목코드별 검색)
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_metadata_company_code
    ON public.dart_rag_documents ((metadata->>'company_code'));
 
-- metadata.report_type 필터링 (공시 유형별 검색: 사업보고서, 분기보고서 등)
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_metadata_report_type
    ON public.dart_rag_documents ((metadata->>'report_type'));
 
-- metadata.period 필터링 (기간별 검색: 2024, 2023Q3 등)
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_metadata_period
    ON public.dart_rag_documents ((metadata->>'period'));
 
-- JSONB 전체 검색용 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_dart_rag_documents_metadata_gin
    ON public.dart_rag_documents USING gin (metadata);
 
-- ── RLS 설정 ─────────────────────────────────────────────────────────
 
ALTER TABLE public.dart_rag_documents ENABLE ROW LEVEL SECURITY;
 
DROP POLICY IF EXISTS "Allow read"  ON public.dart_rag_documents;
CREATE POLICY "Allow read"  ON public.dart_rag_documents
    FOR SELECT TO anon, authenticated USING (true);
 
DROP POLICY IF EXISTS "Allow write" ON public.dart_rag_documents;
CREATE POLICY "Allow write" ON public.dart_rag_documents
    FOR ALL    TO authenticated      USING (true);
 
-- ── 벡터 검색 함수 ────────────────────────────────────────────────────
-- 사용 가능한 필터:
--   filter_company_code  → 특정 종목코드만 검색 (NULL이면 전체)
--   filter_report_type   → 공시 유형 필터 (NULL이면 전체)
--   filter_period        → 기간 필터 (NULL이면 전체)
CREATE OR REPLACE FUNCTION public.match_dart_documents(
    query_embedding     vector(768),
    match_count         int     DEFAULT 5,
    filter_company_code text    DEFAULT NULL,
    filter_report_type  text    DEFAULT NULL,
    filter_period       text    DEFAULT NULL
)
RETURNS TABLE (
    id           bigint,
    chunk_id     text,
    doc_id       text,
    section      text,
    title        text,
    content      text,
    metadata     jsonb,
    similarity   float
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
    FROM public.dart_rag_documents rd
    WHERE
        rd.embedding IS NOT NULL
        AND (filter_company_code IS NULL OR rd.metadata->>'company_code' = filter_company_code)
        AND (filter_report_type  IS NULL OR rd.metadata->>'report_type'  = filter_report_type)
        AND (filter_period       IS NULL OR rd.metadata->>'period'        = filter_period)
    ORDER BY rd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;