import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from services.energy_service import get_all_energy_stats
from utils.preprocessing import (
    to_dataframe,
    clean_dataframe,
    select_feature_columns,
    prepare_scaled_features,
)

FEATURE_COLUMNS = [
    "total_resident_population",
    "total_households",
    "gas_supply_ratio",
    "home_ratio",
    "public_ratio",
    "service_ratio",
    "industry_ratio",
]

_analysis_cache = {
    "correlation": {},
    "elbow": {},
    "silhouette": {},
    "kmeans": {}
}

def clear_analysis_cache():
    global _analysis_cache
    _analysis_cache = {
        "correlation": {},
        "elbow": {},
        "silhouette": {},
        "kmeans": {}
    }

def _make_cache_key(prefix: str, **kwargs) -> str:
    parts = [prefix]
    for key, value in sorted(kwargs.items()):
        parts.append(f"{key}={value}")
    return "|".join(parts)

def _load_all_rows(db):
    rows = get_all_energy_stats(db)
    return rows if rows else []

def _prepare_analysis_frames(db):
    rows = _load_all_rows(db)
    if not rows:
        return None, None, None, None

    raw_df = to_dataframe(rows)
    if raw_df.empty:
        return None, None, None, None

    meta_df = raw_df[["year", "district"]].copy()
    feature_df = select_feature_columns(raw_df)
    feature_df = clean_dataframe(feature_df)

    if feature_df.empty:
        return None, None, None, None

    meta_df = meta_df.loc[feature_df.index].copy()
    scaler_input_rows = raw_df.loc[feature_df.index].to_dict(orient="records")
    df_clean, X_scaled, scaler = prepare_scaled_features(scaler_input_rows)
    df_clean = df_clean[FEATURE_COLUMNS].copy()

    meta_df = meta_df.reset_index(drop=True)
    df_clean = df_clean.reset_index(drop=True)

    return rows, raw_df, meta_df, (df_clean, X_scaled, scaler)

def _year_range(raw_df: pd.DataFrame) -> list[int]:
    return [int(raw_df["year"].min()), int(raw_df["year"].max())]

def _validate_k_range(k_range):
    start_k, end_k = k_range

    if start_k < 2:
        raise ValueError("K의 시작값은 2 이상")
    if end_k < start_k:
        raise ValueError("K의 종료값은 시작값보다 크거나 같아야함")

    return start_k, end_k

def get_optimal_k(db, k_range=(2, 8)):
    result = get_silhouette_scores(db, k_range)

    if result["status"] != "success":
        return result

    best_k = result["data"]["best_k"]

    return {
        "status": "success",
        "data": {
            "recommended_k": best_k,
            "reason": "silhouette_score 기준 최대값"
        }
    }

def _summarize_cluster(cluster_means: pd.Series, overall_means: pd.Series) -> str:
    high_features = []
    low_features = []

    label_map = {
        "total_resident_population": "상주인구",
        "total_households": "가구수",
        "gas_supply_ratio": "가스 보급률",
        "home_ratio": "가정용 비율",
        "public_ratio": "공공용 비율",
        "service_ratio": "서비스업 비율",
        "industry_ratio": "산업용 비율",
    }

    for col in FEATURE_COLUMNS:
        overall = overall_means[col]
        current = cluster_means[col]

        if overall == 0:
            continue

        ratio = current / overall

        if ratio >= 1.15:
            high_features.append(label_map[col])
        elif ratio <= 0.85:
            low_features.append(label_map[col])

    parts = []

    if high_features:
        parts.append(f"상대적으로 높은 항목: {', '.join(high_features[:3])}")
    if low_features:
        parts.append(f"상대적으로 낮은 항목: {', '.join(low_features[:3])}")

    if not parts:
        return "전체 평균과 유사한 복합형 군집"

    return " / ".join(parts)

def get_correlation_matrix(db):
    cache_key = "all_years"

    if cache_key in _analysis_cache["correlation"]:
        return _analysis_cache["correlation"][cache_key]

    prepared = _prepare_analysis_frames(db)
    if prepared[0] is None:
        return {
            "status": "fail",
            "message": "분석 가능한 데이터가 없다."
        }

    _, raw_df, _, processed = prepared
    df_clean, _, _ = processed

    corr = df_clean.corr().round(4)

    result = {
        "status": "success",
        "data": {
            "year_range": _year_range(raw_df),
            "labels": list(corr.columns),
            "matrix": corr.values.tolist(),
        }
    }

    _analysis_cache["correlation"][cache_key] = result
    return result

# 엘보우 계산 
def get_elbow_data(db, k_range=(2, 8)):
    start_k, end_k = _validate_k_range(k_range)
    cache_key = _make_cache_key("all_years", start_k=start_k, end_k=end_k)

    if cache_key in _analysis_cache["elbow"]:
        return _analysis_cache["elbow"][cache_key]

    prepared = _prepare_analysis_frames(db)
    if prepared[0] is None:
        return {
            "status": "fail",
            "message": "분석 가능한 데이터가 없다."
        }

    raw_rows, raw_df, _, processed = prepared
    _, X_scaled, _ = processed

    inertia_list = []

    for k in range(start_k, end_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)

        inertia_list.append({
            "k": k,
            "inertia": round(float(kmeans.inertia_), 4)
        })

    result = {
        "status": "success",
        "data": {
            "year_range": _year_range(raw_df),
            "district_count": len(raw_rows),
            "values": inertia_list,
        }
    }

    _analysis_cache["elbow"][cache_key] = result
    return result

# 실루엣계수
def get_silhouette_scores(db, k_range=(2, 8)):
    start_k, end_k = _validate_k_range(k_range)
    cache_key = _make_cache_key("all_years", start_k=start_k, end_k=end_k)

    if cache_key in _analysis_cache["silhouette"]:
        return _analysis_cache["silhouette"][cache_key]

    prepared = _prepare_analysis_frames(db)
    if prepared[0] is None:
        return {
            "status": "fail",
            "message": "분석 가능한 데이터가 없다."
        }

    _, raw_df, _, processed = prepared
    _, X_scaled, _ = processed

    scores = []

    for k in range(start_k, end_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)

        scores.append({
            "k": k,
            "silhouette_score": round(float(score), 4)
        })

    best_item = max(scores, key=lambda x: x["silhouette_score"])

    result = {
        "status": "success",
        "data": {
            "year_range": _year_range(raw_df),
            "best_k": best_item["k"],
            "best_score": best_item["silhouette_score"],
            "values": scores,
        }
    }

    _analysis_cache["silhouette"][cache_key] = result
    return result

# K-means
def get_kmeans_clusters(db, k=4):
    if k < 2:
        return {
            "status": "fail",
            "message": "K는 2 이상"
        }

    cache_key = _make_cache_key("all_years", k=k)

    if cache_key in _analysis_cache["kmeans"]:
        return _analysis_cache["kmeans"][cache_key]

    prepared = _prepare_analysis_frames(db)
    if prepared[0] is None:
        return {
            "status": "fail",
            "message": "분석 가능한 데이터가 없다."
        }

    raw_rows, raw_df, meta_df, processed = prepared
    df_clean, X_scaled, _ = processed

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    result_df = meta_df.copy()
    result_df["cluster"] = labels

    enriched_df = pd.concat([result_df, df_clean], axis=1)

    cluster_means = enriched_df.groupby("cluster")[FEATURE_COLUMNS].mean().round(4)
    overall_means = enriched_df[FEATURE_COLUMNS].mean()

    cluster_summary = []
    for cluster_id, row in cluster_means.iterrows():
        cluster_rows = enriched_df[enriched_df["cluster"] == cluster_id]
        district_names = sorted(cluster_rows["district"].unique().tolist())

        cluster_summary.append({
            "cluster": int(cluster_id),
            "record_count": int(len(cluster_rows)),
            "districts": district_names,
            "summary": _summarize_cluster(row, overall_means),
            "mean_profile": {
                col: float(row[col]) for col in FEATURE_COLUMNS
            }
        })

    district_result = enriched_df[
        ["year", "district", "cluster"] + FEATURE_COLUMNS
    ].sort_values(by=["cluster", "year", "district"])

    result = {
        "status": "success",
        "data": {
            "year_range": _year_range(raw_df),
            "k": k,
            "record_count": len(raw_rows),
            "districts": district_result.to_dict(orient="records"),
            "cluster_summary": cluster_summary,
        }
    }

    _analysis_cache["kmeans"][cache_key] = result
    return result
