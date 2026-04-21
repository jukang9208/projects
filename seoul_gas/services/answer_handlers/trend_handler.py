from typing import Any
from services.db_service import get_district_trend, search_rag_documents
from services.answer_utils import (
    format_number,
    get_metric_label,
    get_metric_unit,
    get_safe_val,
)

def get_trend_type(start: dict, end: dict) -> str:
    pop_diff = get_safe_val(end, "total_pop") - get_safe_val(start, "total_pop")
    gas_diff = get_safe_val(end, "gas_supply") - get_safe_val(start, "gas_supply")

    if pop_diff < 0 and gas_diff > 0:
        return "인구 감소와 수급 증가"
    if pop_diff > 0 and gas_diff < 0:
        return "인구 증가와 수급 감소"
    if pop_diff < 0 and gas_diff < 0:
        return "동반 감소"
    if pop_diff > 0 and gas_diff > 0:
        return "동반 증가"
    return "정체와 수급 증가"

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

def doc_matches_trend_type(doc: dict, trend_type: str) -> bool:
    title = normalize_text(doc.get("title"))
    section = normalize_text(doc.get("section"))
    chunk_id = normalize_text(doc.get("chunk_id"))
    content = normalize_text(doc.get("content"))
    keywords = doc.get("keywords", [])

    keyword_text = " ".join([normalize_text(k) for k in keywords]) if isinstance(keywords, list) else normalize_text(keywords)
    combined = f"{title} {section} {chunk_id} {content} {keyword_text}"

    if section and section != "trend":
        return False

    return trend_type in combined

def deduplicate_docs(docs: list[dict]) -> list[dict]:
    unique_docs = []
    seen = set()

    for doc in docs:
        key = (
            normalize_text(doc.get("chunk_id")),
            normalize_text(doc.get("title")),
            normalize_text(doc.get("content")),
        )
        if key not in seen:
            unique_docs.append(doc)
            seen.add(key)

    return unique_docs


def pick_primary_trend_doc(trend_type: str) -> list[dict]:
    candidate_queries = [
        trend_type,
        f"{trend_type} 추세 해석",
        f"{trend_type} 원인",
        f"{trend_type} 해석",
    ]

    matched_docs = []

    for query in candidate_queries:
        docs = search_rag_documents(query, match_count=5)
        filtered = [doc for doc in docs if doc_matches_trend_type(doc, trend_type)]
        if filtered:
            matched_docs.extend(filtered)
            break

    return deduplicate_docs(matched_docs)[:1]

def answer_trend(parsed: dict) -> dict[str, Any]:
    district = parsed.get("district")
    metric = parsed.get("metric", "gas_supply")
    label = get_metric_label(metric)
    unit = get_metric_unit(metric)

    trend_list = get_district_trend(district)
    if not trend_list:
        return {"answer": f"{district} 데이터가 없습니다.", "sources": []}

    trend_list = sorted(trend_list, key=lambda x: x.get("year", 0))

    start, end = trend_list[0], trend_list[-1]
    s_val = get_safe_val(start, metric)
    e_val = get_safe_val(end, metric)

    diff = e_val - s_val
    status = "증가" if diff > 0 else "감소" if diff < 0 else "유지"
    diff_pct = (diff / s_val * 100) if s_val != 0 else 0

    db_fact = (
        f"DB 분석 결과, {district}의 {label}는 "
        f"{start['year']}년 {format_number(s_val, unit)}에서 "
        f"{end['year']}년 {format_number(e_val, unit)}으로 "
        f"약 {abs(diff_pct):.1f}% {status}했다."
    )

    trend_type = get_trend_type(start, end)

    primary_docs = pick_primary_trend_doc(trend_type)

    secondary_raw_docs = search_rag_documents(
        f"{district} {label} 변화 추이 해석 원인",
        match_count=5,
    )

    secondary_docs = []
    for doc in secondary_raw_docs:
        if doc_matches_trend_type(doc, trend_type):
            secondary_docs.append(doc)

    docs = deduplicate_docs(primary_docs + secondary_docs)

    primary_text = primary_docs[0].get("content", "").strip() if primary_docs else ""

    secondary_texts = []
    for doc in secondary_docs:
        content = normalize_text(doc.get("content"))
        if content and content != primary_text:
            secondary_texts.append(content)

    secondary_text = " ".join(secondary_texts).strip()

    answer_parts = [db_fact]

    if primary_text:
        answer_parts.append(primary_text)

    if secondary_text:
        answer_parts.append(secondary_text)

    return {
        "intent": "trend",
        "district": district,
        "year": parsed.get("year"),
        "answer": " ".join(answer_parts).strip(),
        "trend": {
            "district": district,
            "type": trend_type,
            "label": label,
            "data": trend_list,
        },
        "sources": docs,
    }