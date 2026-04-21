from typing import Any
from sqlalchemy import text
from db.database import SessionLocal
from services.db_service import seararch_rag_documents
from services.answer_utils import format_number, build_kpi
from services.answer_handlers.llm_client import call_llm, clean_rag

_SUMMARY_PROMPT = """당신은 서울시 에너지 데이터 분석 전문가입니다.
아래 [DB 수치]와 [분석 보고서 내용]을 바탕으로 서울시 전체 에너지 현황을 3~5문장으로 자연스럽게 요약하세요.

규칙:
- 수치는 DB 수치를 우선 사용
- 분석 보고서의 인사이트(군집 특성, 추세, 구조적 해석)를 자연스럽게 포함
- 차트 눈금, 그래프 레이블, 반복 문장은 제거
- 한국어로 작성, 존댓말 사용 금지
- 요약문만 출력 (별도 제목, 마크다운 불필요)

[DB 수치]
{db_fact}

[분석 보고서 내용]
{rag_text}
"""


def answer_seoul_summary(parsed: dict) -> dict[str, Any]:
    year = parsed.get("year") or 2024

    db = SessionLocal()
    try:
        query = text("""
            SELECT
                SUM(home_usage)                AS home_usage,
                SUM(public_usage)              AS public_usage,
                SUM(service_usage)             AS service_usage,
                SUM(industry_usage)            AS industry_usage,
                SUM(total_resident_population) AS total_resident_population
            FROM seoul_district_energy_stats
            WHERE year = :year
        """)
        result = db.execute(query, {"year": year})
        row = result.fetchone()
    finally:
        db.close()

    if not row or row[0] is None:
        return {
            "intent":   "seoul_summary",
            "district": "서울 전체",
            "year":     year,
            "answer":   f"{year}년 서울시 전체 데이터를 불러올 수 없습니다.",
            "kpi":      None,
            "sources":  [],
            "rag_docs": [],
        }

    stats = {
        "home_usage":                float(row.home_usage or 0),
        "public_usage":              float(row.public_usage or 0),
        "service_usage":             float(row.service_usage or 0),
        "industry_usage":            float(row.industry_usage or 0),
        "total_resident_population": float(row.total_resident_population or 0),
    }
    total      = sum(stats[k] for k in ["home_usage", "public_usage", "service_usage", "industry_usage"])
    population = stats["total_resident_population"]
    district_count = 25

    db_fact = (
        f"{year}년 서울시 전체 전력사용량: {format_number(total, 'MWh')} "
        f"(가정용 {format_number(stats['home_usage'], 'MWh')}, "
        f"공공용 {format_number(stats['public_usage'], 'MWh')}, "
        f"서비스업 {format_number(stats['service_usage'], 'MWh')}, "
        f"산업용 {format_number(stats['industry_usage'], 'MWh')}). "
        f"자치구별 평균 {format_number(total / district_count, 'MWh')}. "
        f"총 상주인구 {format_number(population, '명')} "
        f"(자치구별 평균 {format_number(population / district_count, '명')})."
    )

    docs     = seararch_rag_documents("서울시 에너지 소비 현황 군집 특성 추세", match_count=5)
    rag_text = clean_rag(docs, max_lines=100) or "(RAG 문서 없음 — DB 수치 기반으로만 요약)"

    prompt  = _SUMMARY_PROMPT.format(db_fact=db_fact, rag_text=rag_text)
    summary = call_llm(prompt, fallback=db_fact, handler_name="seoul_handler")

    return {
        "intent":   "seoul_summary",
        "district": "서울 전체",
        "year":     year,
        "answer":   summary,
        "kpi":      build_kpi(stats),
        "sources":  docs,
        "rag_docs": docs,
    }
