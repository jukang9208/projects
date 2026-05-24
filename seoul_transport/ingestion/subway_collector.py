import requests
import pandas as pd
from pathlib import Path
from core.config import settings
from datetime import datetime, timedelta


SEOUL_SUBWAY_URL      = "http://openapi.seoul.go.kr:8088/{key}/json/CardSubwayStatsNew/{start}/{end}/{date}/"
SEOUL_HOURLY_URL      = "http://openapi.seoul.go.kr:8088/{key}/json/CardSubwayTime/{start}/{end}/{month}/"


def fetch_subway_data(start_idx: int = 1, end_idx: int = 1000, date: str = None) -> pd.DataFrame:

    if date is None:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    url = SEOUL_SUBWAY_URL.format(
        key=settings.SEOUL_API_KEY,
        start=start_idx,
        end=end_idx,
        date=date
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    rows = data.get("CardSubwayStatsNew", {}).get("row", [])
    return pd.DataFrame(rows)


def save_raw_local(df: pd.DataFrame, date: str) -> str:
    
    path = Path(settings.RAW_PATH) / "subway" / date[:6]
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"subway_{date}.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"[subway_collector] saved local → {file_path} ({len(df)} rows)")
    return str(file_path)


def save_raw_gcs(df: pd.DataFrame, date: str) -> str:
    
    from google.cloud import storage

    blob_path = f"raw/subway/{date[:6]}/subway_{date}.csv"
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

    client = storage.Client(project=settings.GCS_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(csv_bytes, content_type="text/csv")

    gcs_path = f"gs://{settings.GCS_BUCKET_NAME}/{blob_path}"
    print(f"[subway_collector] saved GCS → {gcs_path} ({len(df)} rows)")
    return gcs_path


def save_raw(df: pd.DataFrame, date: str) -> str:
    
    if settings.use_gcs:
        return save_raw_gcs(df, date)
    return save_raw_local(df, date)


def run(date: str = None):
    df = fetch_subway_data(date=date)
    if df.empty:
        print("[subway_collector] 데이터 없음")
        return None   # pipeline에서 None 체크용
    today = date or (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    return save_raw(df, today)


# 시간대별 승하차 수집 (월별) 
def fetch_hourly_data(month: str = None, page_size: int = 1000) -> pd.DataFrame:

    if month is None:
        first_of_month = datetime.now().replace(day=1)
        month = (first_of_month - timedelta(days=1)).strftime("%Y%m")

    all_rows = []
    start = 1

    while True:
        end = start + page_size - 1
        url = SEOUL_HOURLY_URL.format(
            key=settings.SEOUL_API_KEY,
            start=start,
            end=end,
            month=month,
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        # 빈 응답 or XML 오류 처리
        text = resp.text.strip()
        if not text or text.startswith("<"):
            break

        data = resp.json()
        result_code = data.get("CardSubwayTime", {}).get("RESULT", {}).get("CODE", "")
        if result_code and result_code != "INFO-000":
            break

        rows = data.get("CardSubwayTime", {}).get("row", [])
        if not rows:
            break

        all_rows.extend(rows)

        total = data.get("CardSubwayTime", {}).get("list_total_count", 0)
        if end >= total:
            break
        start = end + 1

    return pd.DataFrame(all_rows)


def save_hourly_local(df: pd.DataFrame, month: str) -> str:
    path = Path(settings.RAW_PATH) / "subway_hourly"
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"subway_hourly_{month}.csv"
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"[hourly_collector] saved local → {file_path} ({len(df)} rows)")
    return str(file_path)


def save_hourly_gcs(df: pd.DataFrame, month: str) -> str:
    from google.cloud import storage
    blob_path = f"raw/subway_hourly/subway_hourly_{month}.csv"
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    client = storage.Client(project=settings.GCS_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    bucket.blob(blob_path).upload_from_string(csv_bytes, content_type="text/csv")
    gcs_path = f"gs://{settings.GCS_BUCKET_NAME}/{blob_path}"
    print(f"[hourly_collector] saved GCS → {gcs_path} ({len(df)} rows)")
    return gcs_path


def run_hourly(month: str = None):
    
    df = fetch_hourly_data(month=month)
    if df.empty:
        print(f"[hourly_collector] {month} 데이터 없음")
        return None
    target = month or (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    if settings.use_gcs:
        return save_hourly_gcs(df, target)
    return save_hourly_local(df, target)
