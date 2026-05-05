import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from core.config import settings
from core.spark import get_spark_local
from ingestion.subway_collector import run as collect
from spark_jobs.subway_transform import raw_to_silver, silver_to_gold_congestion, silver_to_gold_transfer


def run_pipeline(date: str = None):

    if date is None:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"\n{'='*50}")
    print(f"서울 지하철 파이프라인 시작: {date}")
    print(f"{'='*50}\n")

    # 데이터 수집
    print("[1/3] 서울 API에서 데이터 수집 중...")
    collect(date=date)
    print(f"수집 완료 → data/raw/subway/{date[:6]}/subway_{date}.csv\n")

    # Spark 변환
    print("[2/3] Spark 파이프라인 실행 중...")
    spark = get_spark_local()
    spark.sparkContext.setLogLevel("ERROR")

    raw_to_silver(spark, date)
    silver_to_gold_congestion(spark)
    silver_to_gold_transfer(spark)

    # 결과 확인
    print("[3/3] 결과 확인...")
    df_silver = spark.read.format("delta").load(settings.SILVER_PATH + "/subway")
    df_gold   = spark.read.format("delta").load(settings.GOLD_PATH + "/congestion_daily_avg")
    df_trans  = spark.read.format("delta").load(settings.GOLD_PATH + "/transfer_stations")

    print(f"  Silver 총 행수 : {df_silver.count():,}")
    print(f"  Gold(역별평균) : {df_gold.count():,}")
    print(f"  환승역 수      : {df_trans.count()}")

    spark.stop()
    print(f"\n파이프라인 완료!")


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(date=date_arg)
