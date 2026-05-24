import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.spark import get_spark_api
from ingestion.subway_collector import run as collect
from spark_jobs.subway_transform import (
    raw_to_silver,
    silver_to_gold_incremental,
)

# Cloud Run 컨테이너는 UTC → KST(+9) 변환 필요
KST = timezone(timedelta(hours=9))


def main():
    # RUN_DATE 환경변수 우선, 없으면 KST 기준 3일 전 (API 제공 지연 반영)
    date = os.environ.get("RUN_DATE") or (datetime.now(KST) - timedelta(days=3)).strftime("%Y%m%d")

    print(f"[pipeline] 실행 날짜: {date} (KST 기준)")

    print("[pipeline] Step 1: 데이터 수집")
    result = collect(date=date)
    if result is None:
        print(f"[pipeline] {date} 데이터 없음 — 정상 종료")
        sys.exit(0)

    print("[pipeline] Step 2: Spark 변환")
    spark = get_spark_api()
    raw_to_silver(spark, date)
    silver_to_gold_incremental(spark, date)

    spark.stop()
    print(f"[pipeline] {date} 완료")


if __name__ == "__main__":
    main()
