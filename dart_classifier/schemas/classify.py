from pydantic import BaseModel, Field


# ── Classify ──────────────────────────────────────────────
class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=10, description="분류할 공시 본문 텍스트")


class ClassifyResult(BaseModel):
    label: str = Field(..., description="예측 카테고리 (감사보고서 / 사업보고서 / 유상증자)")
    score: float = Field(..., description="예측 신뢰도 (0~1)")


class ClassifyResponse(BaseModel):
    result: ClassifyResult
    text_length: int = Field(..., description="입력 텍스트 길이")


# ── RAG Ingest ────────────────────────────────────────────
class IngestRequest(BaseModel):
    chunk_id: str       = Field(..., description="청크 고유 ID")
    doc_id: str         = Field(..., description="원문 공시 문서 ID (rcept_no 등)")
    content: str        = Field(..., min_length=10, description="본문 텍스트")
    title: str | None   = Field(None, description="공시 제목")
    section: str | None = Field(None, description="섹션명")
    metadata: dict | None = Field(None, description="company_code, report_type, period 등")


class IngestBatchRequest(BaseModel):
    documents: list[IngestRequest] = Field(..., description="ingest할 청크 리스트")


class IngestResponse(BaseModel):
    chunk_id: str
    message: str = "ok"


# ── RAG Search ────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str            = Field(..., min_length=2, description="검색 쿼리")
    match_count: int      = Field(3, ge=1, le=20, description="반환 청크 수")
    company_code: str | None = Field(None, description="종목코드 필터")
    report_type: str | None  = Field(None, description="공시 유형 필터")
    period: str | None       = Field(None, description="기간 필터 (예: 2024, 2023Q3)")


class SearchResult(BaseModel):
    id: int
    chunk_id: str
    doc_id: str
    section: str | None
    title: str | None
    content: str
    metadata: dict
    similarity: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    count: int


# ── Analyze (분류 + 재무) ─────────────────────────────────
class AnalyzeRequest(BaseModel):
    text:      str = Field(..., min_length=10, description="공시 본문 텍스트")
    corp_name: str = Field(..., min_length=1,  description="기업명")
    year:      int = Field(..., ge=2015, le=2030, description="사업연도")


class FinancialData(BaseModel):
    corp_name:         str
    stock_code:        str | None  = Field(None, description="종목코드")
    year:              int
    # 재무제표
    revenue:           int | None  = Field(None, description="매출액 (원)")
    operating_profit:  int | None  = Field(None, description="영업이익 (원)")
    net_income:        int | None  = Field(None, description="당기순이익 (원)")
    total_assets:      int | None  = Field(None, description="자산총계 (원)")
    total_liabilities: int | None  = Field(None, description="부채총계 (원)")
    total_equity:      int | None  = Field(None, description="자본총계 (원)")
    debt_ratio:        float | None = Field(None, description="부채비율 (%)")
    # 주가
    close:             int | None  = Field(None, description="최신 종가 (원)")
    market_cap:        int | None  = Field(None, description="시가총액 (원)")
    high_52w:          int | None  = Field(None, description="52주 최고가 (원)")
    low_52w:           int | None  = Field(None, description="52주 최저가 (원)")
    listed:            bool        = Field(False, description="상장 여부")
    source:            str         = Field(..., description="cache | dart_api")


class AnalyzeResponse(BaseModel):
    classify:  ClassifyResult
    financial: FinancialData
    insight:   str = Field(..., description="분류 + 재무 기반 종합 인사이트")
