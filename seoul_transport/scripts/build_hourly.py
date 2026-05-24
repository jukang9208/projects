import os
import sys
import glob
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.config import settings
from core.spark import get_spark_local
from ingestion.subway_collector import fetch_hourly_data, save_hourly_local
from spark_jobs.subway_transform import _HOURS
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def _hourly_raw_to_silver_local(spark: SparkSession, month: str, raw_root: str, silver_root: str):
    from delta.tables import DeltaTable

    raw_path    = f"{raw_root}/subway_hourly/subway_hourly_{month}.csv"
    silver_path = f"{silver_root}/subway_hourly"

    df = spark.read.csv(raw_path, header=True, inferSchema=False)

    # API 응답이 '775.0' 형태 소수점 문자열 → DOUBLE 경유 LONG 캐스팅
    stack_items = ", ".join([
        f"{h}, CAST(CAST(`HR_{h}_GET_ON_NOPE` AS DOUBLE) AS LONG), CAST(CAST(`HR_{h}_GET_OFF_NOPE` AS DOUBLE) AS LONG)"
        for h in _HOURS
    ])
    stack_expr = f"stack({len(_HOURS)}, {stack_items}) AS (hour, ride_num, alight_num)"

    df_long = df.select(
        F.col("USE_MM").alias("use_mm"),
        F.col("SBWY_ROUT_LN_NM").alias("line_num"),
        F.col("STTN").alias("subway_sta_nm"),
        F.expr(stack_expr),
    ).dropna(subset=["use_mm", "line_num", "subway_sta_nm"]) \
     .fillna(0, subset=["ride_num", "alight_num"])

    if DeltaTable.isDeltaTable(spark, silver_path):
        DeltaTable.forPath(spark, silver_path).alias("t").merge(
            df_long.alias("n"),
            "t.use_mm = n.use_mm AND t.line_num = n.line_num "
            "AND t.subway_sta_nm = n.subway_sta_nm AND t.hour = n.hour"
        ).whenNotMatchedInsertAll().execute()
        cnt = spark.read.format("delta").load(silver_path).filter(
            F.col("use_mm") == month
        ).count()
    else:
        df_long.write.format("delta").mode("overwrite").partitionBy("use_mm").save(silver_path)
        cnt = df_long.count()

    print(f"  [Silver] {month} 완료 ({cnt} rows)")


def _silver_to_gold_hourly_local(spark: SparkSession, silver_root: str, gold_root: str):
    from pyspark.sql.window import Window

    silver_path = f"{silver_root}/subway_hourly"
    df = spark.read.format("delta").load(silver_path)

    # CardSubwayTime API는 월 누계 총량 → 해당 월 일수로 나눠 일 평균으로 변환
    df = df.withColumn(
        "days_in_month",
        F.dayofmonth(F.last_day(F.to_date(F.concat(F.col("use_mm"), F.lit("01")), "yyyyMMdd")))
    )

    # 역·호선·시간대별 일 평균 승하차
    df.groupBy("line_num", "subway_sta_nm", "hour") \
        .agg(
            F.avg(F.col("ride_num")   / F.col("days_in_month")).alias("avg_ride"),
            F.avg(F.col("alight_num") / F.col("days_in_month")).alias("avg_alight"),
            F.max(F.col("ride_num")   / F.col("days_in_month")).alias("max_ride"),
            F.count("use_mm").alias("data_months"),
        ) \
        .write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
        .save(f"{gold_root}/congestion_hourly_avg")
    print("  [Gold] congestion_hourly_avg 완료")

    # 피크타임 (역별 승차 상위 3시간대)
    w = Window.partitionBy("subway_sta_nm").orderBy(F.col("avg_ride").desc())
    df_hourly = spark.read.format("delta").load(f"{gold_root}/congestion_hourly_avg")
    df_hourly \
        .groupBy("subway_sta_nm", "hour") \
        .agg(F.avg("avg_ride").alias("avg_ride")) \
        .withColumn("rank", F.rank().over(w)) \
        .filter(F.col("rank") <= 3).drop("rank") \
        .write.format("delta").mode("overwrite") \
        .save(f"{gold_root}/congestion_peak_hours")
    print("  [Gold] congestion_peak_hours 완료")


def get_available_months(start: str = None, end: str = None) -> list[str]:
    # 매월 5일 이후 전달 데이터 제공; 기본 범위: 최근 2년
    today = datetime.now()
    if today.day >= 5:
        last_available = today.replace(day=1) - timedelta(days=1)
    else:
        last_available = today.replace(day=1) - timedelta(days=1)
        last_available = last_available.replace(day=1) - timedelta(days=1)

    first = start or (today.replace(year=today.year - 2)).strftime("%Y%m")
    last  = end   or last_available.strftime("%Y%m")

    months = []
    cur = datetime.strptime(first + "01", "%Y%m%d")
    end_dt = datetime.strptime(last + "01", "%Y%m%d")
    while cur <= end_dt:
        months.append(cur.strftime("%Y%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def get_collected_months() -> set:
    # 로컬 파일 기준 수집 여부 확인
    collected = set()
    pattern = f"{settings.RAW_PATH}/subway_hourly/subway_hourly_*.csv"
    for f in glob.glob(pattern):
        m = os.path.basename(f).replace("subway_hourly_", "").replace(".csv", "")
        if len(m) == 6 and m.isdigit():
            collected.add(m)
    return collected


def _get_collected_months_gcs() -> set:
    # GCS 버킷에서 이미 수집된 월 확인
    from google.cloud import storage
    client = storage.Client(project=settings.GCS_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET_NAME)
    blobs  = bucket.list_blobs(prefix="raw/subway_hourly/subway_hourly_")
    collected = set()
    for blob in blobs:
        m = os.path.basename(blob.name).replace("subway_hourly_", "").replace(".csv", "")
        if len(m) == 6 and m.isdigit():
            collected.add(m)
    return collected


def get_missing_months(start: str = None, end: str = None) -> list[str]:
    all_months = get_available_months(start, end)
    collected  = get_collected_months()
    return [m for m in all_months if m not in collected]


def run(start: str = None, end: str = None):
    use_gcs = settings.use_gcs

    if use_gcs:
        from core.spark import get_spark_api
        from ingestion.subway_collector import save_hourly_gcs
        from spark_jobs.subway_transform import hourly_raw_to_silver, silver_to_gold_hourly
        spark = get_spark_api()
    else:
        spark = get_spark_local()

    spark.sparkContext.setLogLevel("ERROR")

    all_months = get_available_months(start, end)

    # ── 1. 미수집 월 API 수집 ────────────────────────────────────────
    existing = _get_collected_months_gcs() if use_gcs else get_collected_months()
    missing  = [m for m in all_months if m not in existing]

    if missing:
        print(f"\n{'='*50}")
        print(f"API 수집: {missing[0]} ~ {missing[-1]} ({len(missing)}개월)")
        print(f"{'='*50}\n")
        for month in missing:
            df = fetch_hourly_data(month=month)
            if df.empty:
                print(f"  [SKIP] {month} - 데이터 없음")
                continue
            if use_gcs:
                save_hourly_gcs(df, month)
            else:
                save_hourly_local(df, month)

    # ── 2. Silver 빌드 ───────────────────────────────────────────────
    # 수집 완료 후 실제 존재하는 월 재확인 (SKIP된 월 제외)
    after_collect = _get_collected_months_gcs() if use_gcs else get_collected_months()
    months_to_build = [m for m in all_months if m in after_collect]

    if not months_to_build:
        print("처리할 raw 데이터 없음")
        spark.stop()
        return

    print(f"\n{'='*50}")
    print(f"Silver 빌드: {months_to_build[0]} ~ {months_to_build[-1]} ({len(months_to_build)}개월)")
    print(f"{'='*50}\n")

    built = []
    for month in months_to_build:
        try:
            if use_gcs:
                hourly_raw_to_silver(spark, month)
            else:
                _hourly_raw_to_silver_local(spark, month, settings.RAW_PATH, settings.SILVER_PATH)
            built.append(month)
        except Exception as e:
            print(f"  [ERROR] {month} Silver 빌드 실패: {e}")
            import traceback
            traceback.print_exc()

    if not built:
        print("\nSilver 빌드 실패 — Gold 생략")
        spark.stop()
        return

    # ── 3. Gold 빌드 ─────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print("Gold 빌드 시작")
    print(f"{'='*50}\n")

    if use_gcs:
        silver_to_gold_hourly(spark)
        gold_path = settings.effective_gold_path
    else:
        _silver_to_gold_hourly_local(spark, settings.SILVER_PATH, settings.GOLD_PATH)
        gold_path = settings.GOLD_PATH

    df  = spark.read.format("delta").load(f"{gold_path}/congestion_hourly_avg")
    row = df.agg(F.min("hour"), F.max("hour"), F.countDistinct("subway_sta_nm")).collect()[0]
    print(f"\n  hourly_avg 행수    : {df.count():,}")
    print(f"  시간대 범위        : {row[0]}시 ~ {row[1]}시")
    print(f"  역 수              : {row[2]}")

    spark.stop()
    print("\n시간대별 Lakehouse 빌드 완료!")


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else None
    e = sys.argv[2] if len(sys.argv) > 2 else None
    run(s, e)
