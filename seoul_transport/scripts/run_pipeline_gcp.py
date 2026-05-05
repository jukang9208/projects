import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.spark import get_spark_api
from ingestion.subway_collector import run as collect
from spark_jobs.subway_transform import (
    raw_to_silver,
    silver_to_gold_congestion,
    silver_to_gold_transfer,
)


def main():
    date = os.environ.get("RUN_DATE") or \
           (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"[pipeline] 실행 날짜: {date}")

    # 수집
    print("[pipeline] Step 1: 데이터 수집")
    collect(date=date)

    # 변환
    print("[pipeline] Step 2: Spark 변환")
    spark = get_spark_api()
    raw_to_silver(spark, date)
    silver_to_gold_congestion(spark)
    silver_to_gold_transfer(spark)

    spark.stop()
    print("[pipeline] 완료")


if __name__ == "__main__":
    main()
