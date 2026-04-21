import numpy as np


def get_cluster_label_from_profile(cluster_summary: dict, cluster_id: int) -> str:

    home = float(cluster_summary.get("home_ratio_avg") or 0)
    service = float(cluster_summary.get("service_ratio_avg") or 0)
    industry= float(cluster_summary.get("industry_ratio_avg") or 0)
    public = float(cluster_summary.get("public_ratio_avg") or 0)
    pop = float(cluster_summary.get("population_avg") or 0)

    dominant = max(
        ("가정용", home),
        ("서비스업", service),
        ("산업용", industry),
        ("공공용", public),
        key=lambda x: x[1],
    )[0]

    if dominant == "가정용":
        if home >= 0.35:
            return "주거 밀집 지역"
        elif public >= 0.10:
            return "주거·공공 혼재 지역"
        else:
            return "전통 주거 중심 지역"

    if dominant == "서비스업":
        if service >= 0.40:
            return "광역 상업 거점 지역"
        elif industry >= 0.25:
            return "서비스·산업 복합 지역"
        else:
            return "상업 중심 지역"

    if dominant == "산업용":
        if industry >= 0.35:
            return "산업·제조 특화 지역"
        else:
            return "도심 산업·상업 혼합 지역"

    if dominant == "공공용":
        return "공공·행정 기능 중심 지역"

    return f"군집 {cluster_id}"

def format_number(val, unit: str = "") -> str:
    try:
        return f"{int(round(float(val))):,}{unit}"
    except Exception:
        return "-"

def format_ratio(val, unit: str = "") -> str:
    try:
        if unit:
            return f"{int(round(float(val))):,}{unit}"
        return f"{float(val):.4f}"
    except Exception:
        return "-"

def get_metric_label(metric: str) -> str:
    labels = {
        "total_usage": "전체 전력사용량",
        "gas_supply": "가스 수급가구수",
        "gas_supply_ratio": "가스 보급률",
        "total_resident_population": "총상주인구",
        "total_households": "총가구수",
        "home_ratio": "가정용 전력 비율",
        "public_ratio": "공공용 전력 비율",
        "service_ratio": "서비스업 전력 비율",
        "industry_ratio": "산업용 전력 비율",
        "home_usage": "가정용 전력사용량",
        "public_usage": "공공용 전력사용량",
        "service_usage": "서비스업 전력사용량",
        "industry_usage": "산업용 전력사용량",
    }
    return labels.get(metric, metric)

def get_metric_unit(metric: str) -> str:
    if metric in ("total_resident_population",):
        return "명"
    if metric in ("total_households", "gas_supply"):
        return "가구"
    if metric in ("home_usage", "public_usage", "service_usage", "industry_usage", "total_usage"):
        return "MWh"
    return ""

_USAGE_KEYS = ["home_usage", "public_usage", "service_usage", "industry_usage"]

def build_kpi(stats: dict | None) -> list[dict] | None:

    if stats is None:
        return None
    home     = get_safe_val(stats, "home_usage")
    public   = get_safe_val(stats, "public_usage")
    service  = get_safe_val(stats, "service_usage")
    industry = get_safe_val(stats, "industry_usage")
    total    = home + public + service + industry
    pop      = get_safe_val(stats, "total_resident_population")
    return [
        {"key": "total_usage",               "label": "전체 전력사용량", "value": round(total),    "unit": "MWh"},
        {"key": "home_usage",                "label": "가정용",          "value": round(home),     "unit": "MWh"},
        {"key": "public_usage",              "label": "공공용",          "value": round(public),   "unit": "MWh"},
        {"key": "service_usage",             "label": "서비스업",        "value": round(service),  "unit": "MWh"},
        {"key": "industry_usage",            "label": "산업용",          "value": round(industry), "unit": "MWh"},
        {"key": "total_resident_population", "label": "총상주인구",      "value": round(pop),      "unit": "명"},
    ]


def get_safe_val(data_dict: dict, key: str) -> float:
    val = data_dict.get(key)
    return float(val) if val is not None else 0.0

def to_python_type(value):
    if isinstance(value, (np.integer, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float64)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {k: to_python_type(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_python_type(v) for v in value]
    return value