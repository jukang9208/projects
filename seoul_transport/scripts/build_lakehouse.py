import os
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.config import settings
from core.spark import get_spark_local, get_spark_api
from spark_jobs.subway_transform import raw_to_silver, silver_to_gold_congestion, silver_to_gold_transfer


def get_dates_local(start: str = None, end: str = None):
    
    pattern = os.path.join(settings.RAW_PATH, "subway", "**", "subway_*.csv")
    dates = []
    for f in glob.glob(pattern, recursive=True):
        date = os.path.basename(f).replace("subway_", "").replace(".csv", "")
        if len(date) == 8 and date.isdigit():
            if start and date < start:
                continue
            if end and date > end:
                continue
            dates.append(date)
    return sorted(dates)


def get_dates_gcs(start: str = None, end: str = None):
    
    from google.cloud import storage
    client = storage.Client(project=settings.GCS_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blobs = bucket.list_blobs(prefix="raw/subway/")
    dates = []
    for blob in blobs:
        name = blob.name.split("/")[-1]  # subway_YYYYMMDD.csv
        if name.startswith("subway_") and name.endswith(".csv"):
            date = name.replace("subway_", "").replace(".csv", "")
            if len(date) == 8 and date.isdigit():
                if start and date < start:
                    continue
                if end and date > end:
                    continue
                dates.append(date)
    return sorted(dates)


def run(start: str = None, end: str = None):
    if settings.use_gcs:
        dates = get_dates_gcs(start, end)
        spark = get_spark_api()
    else:
        dates = get_dates_local(start, end)
        spark = get_spark_local()

    if not dates:
        print("처리할 Raw 파일 없음")
        return

    print(f"\n{'='*50}")
    print(f"Lakehouse 빌드 시작: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")
    print(f"저장소: {'GCS (' + settings.GCS_BUCKET_NAME + ')' if settings.use_gcs else '로컬'}")
    print(f"{'='*50}\n")

    spark.sparkContext.setLogLevel("ERROR")

    # Raw → Silver (날짜별)
    print(f"[1/2] Raw → Silver ({len(dates)}개 날짜)")
    for date in dates:
        try:
            raw_to_silver(spark, date)
        except Exception as e:
            print(f"  [SKIP] {date} - {e}")

    # Silver → Gold (전체 재집계)
    print("\n[2/2] Silver → Gold 재집계")
    silver_to_gold_congestion(spark)
    silver_to_gold_transfer(spark)

    # 결과 확인
    df_silver = spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")
    df_gold   = spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_daily_avg")
    df_trans  = spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_stations")
    print(f"\n  Silver 총 행수 : {df_silver.count():,}")
    print(f"  Gold(역별평균) : {df_gold.count():,}")
    print(f"  환승역 수      : {df_trans.count()}")

    spark.stop()
    print(f"\n빌드 완료!")


if __name__ == "__main__":
    start_arg = sys.argv[1] if len(sys.argv) > 1 else None
    end_arg   = sys.argv[2] if len(sys.argv) > 2 else None
    run(start_arg, end_arg)
