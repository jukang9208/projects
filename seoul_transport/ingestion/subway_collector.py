import requests
import pandas as pd
from pathlib import Path
from core.config import settings
from datetime import datetime, timedelta


SEOUL_SUBWAY_URL = "http://openapi.seoul.go.kr:8088/{key}/json/CardSubwayStatsNew/{start}/{end}/{date}/"


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
        return
    today = date or (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    save_raw(df, today)
