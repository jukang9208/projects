import re
from typing import Any

def extract_districts(question: str) -> list[str]:
    # 1. '두 글자 이상의 한글 + 구' 형태만 추출 (예: 동작구, 관악구)
    raw_found = re.findall(r"([가-힣]{2,}구)", question)
    
    # 2. [핵심] 자치구가 아닌데 '구'로 끝나는 단어들을 제외하는 필터링
    # '가구', '가구수', '수급가구' 등이 리스트에 들어가는 것을 방지합니다.
    forbidden_words = ["가구", "가구수", "수급가구", "가구수변화"]
    clean_districts = [d for d in raw_found if d not in forbidden_words]
    
    # 3. 중복 제거
    return list(dict.fromkeys(clean_districts))

def detect_metric_from_question(question: str) -> str:
    if any(k in question for k in ["소득", "수입", "벌이", "급여"]):
        return "avg_income"
    if any(k in question for k in ["인구", "명수", "주민"]):
        return "total_pop"
    if any(k in question for k in ["수급", "가스", "공급"]):
        return "gas_supply"
    if any(k in question for k in ["가구수", "세대수", "집수"]):
        return "total_households"
    return "gas_supply"

def parse_question(question: str) -> dict[str, Any]:
    districts = extract_districts(question)
    metric = detect_metric_from_question(question)
    
    # 연도 추출
    year_match = re.search(r"(20\d{2})년?", question)
    # 클러스터 ID 추출
    cluster_match = re.search(r"(?:클러스터|cluster|군집)\s*(\d+)", question, re.IGNORECASE)
    
    return {
        "question": question,
        "year": int(year_match.group(1)) if year_match else None,
        "district": districts[0] if districts else None,
        "districts": districts,
        "metric": metric, 
        "cluster_id": int(cluster_match.group(1)) if cluster_match else None,
    }