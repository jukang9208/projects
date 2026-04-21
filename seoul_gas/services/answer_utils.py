import numpy as np

CLUSTER_LABELS = {
    0: "고소득 다인가구 주거지",
    1: "표준 중산층 주거지",
    2: "소규모 1~2인 가구 지역",
    3: "대규모 1~2인 가구 혼합지역",
}

def format_number(val, unit: str = "") -> str:
    try:
        return f"{int(round(float(val))):,}{unit}"
    except Exception:
        return "-"

def get_metric_label(metric: str) -> str:
    labels = {
        "gas_supply": "가정용 도시가스 수급가구수",
        "avg_income": "월 평균 소득",
        "total_pop": "총인구",
        "total_households": "총가구수",
    }
    return labels.get(metric, metric)

def get_metric_unit(metric: str) -> str:
    if metric == "avg_income":
        return "원"
    if metric == "total_pop":
        return "명"
    return "가구"

def get_safe_val(data_dict: dict, key: str) -> float:
    val = data_dict.get(key)
    if val is None and key == "avg_income":
        val = data_dict.get("income")
    return float(val) if val is not None else 0.0


def to_python_type(value):
    if isinstance(value, (np.integer, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float64)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {k: to_python_type(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_python_type(v) for v in value]
    return value