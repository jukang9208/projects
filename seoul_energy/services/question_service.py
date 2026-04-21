import re
from typing import Any

_SEOUL_DISTRICTS = {
    "강남구", "강동구", "강북구", "강서구", "관악구",
    "광진구", "구로구", "금천구", "노원구", "도봉구",
    "동대문구", "동작구", "마포구", "서대문구", "서초구",
    "성동구", "성북구", "송파구", "양천구", "영등포구",
    "용산구", "은평구", "종로구", "중구", "중랑구",
}

def extract_districts(question: str) -> list[str]:
    found = re.findall(r"([가-힣]{2,}구)", question)
    return list(dict.fromkeys(d for d in found if d in _SEOUL_DISTRICTS))

def detect_metric_from_question(question: str) -> str:
    if any(k in question for k in ["전체 전력", "총 전력", "전력 전체", "전체 사용량", "총 사용량"]):
        return "total_usage"
    if any(k in question for k in ["가정용", "가정 전력"]):
        return "home_usage"
    if any(k in question for k in ["서비스", "상업"]):
        return "service_usage"
    if any(k in question for k in ["산업", "공업", "제조"]):
        return "industry_usage"
    if any(k in question for k in ["공공", "관공서"]):
        return "public_usage"
    if any(k in question for k in ["보급률", "가스 보급", "수급 비율"]):
        return "gas_supply_ratio"
    if any(k in question for k in ["가스", "수급"]):
        return "gas_supply"
    if any(k in question for k in ["인구", "주민", "상주"]):
        return "total_resident_population"
    if any(k in question for k in ["가구수", "세대수"]):
        return "total_households"
    return "total_usage"

def parse_question(question: str) -> dict[str, Any]:
    districts = extract_districts(question)
    metric = detect_metric_from_question(question)
    year_match = re.search(r"(20\d{2})년?", question)
    cluster_match = re.search(r"(?:클러스터|cluster|군집|집단)\s*(\d+)", question, re.IGNORECASE)

    return {
        "question" : question,
        "year" : int(year_match.group(1)) if year_match else None,
        "district" : districts[0] if districts else None,
        "districts" : districts,
        "metric" : metric,
        "cluster_id" : int(cluster_match.group(1)) if cluster_match else None,
    }