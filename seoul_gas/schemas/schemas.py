from typing import Any, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str

class SourceItem(BaseModel):
    type: Optional[str] = None
    section: Optional[str] = None
    chunk_id: Optional[str] = None
    title: Optional[str] = None

class KPIItem(BaseModel):
    key: str
    label: str
    value: Optional[float | int] = None
    unit: Optional[str] = None

class TrendPoint(BaseModel):
    year: int
    value: Optional[float | int] = None

class TrendSeries(BaseModel):
    key: str
    label: str
    unit: Optional[str] = None
    data: list[TrendPoint] = []

class Sections(BaseModel):
    kpi: Optional[list[KPIItem]] = None
    trend: Optional[dict[str, Any]] = None
    cluster: Optional[dict[str, Any]] = None
    comparison: Optional[dict[str, Any]] = None
    correlation: Optional[dict[str, Any]] = None
    map: Optional[dict[str, Any]] = None
    overview: Optional[dict[str, Any]] = None
    rag: Optional[dict[str, Any]] = None
    cluster_list: Optional[dict[str, Any]] = None

class QueryResponse(BaseModel):
    question: str
    query_type: str
    district: Optional[str] = None
    year: Optional[int] = None
    summary: str
    sections: Sections = Field(default_factory=Sections)
    sources: list[SourceItem] = Field(default_factory=list)