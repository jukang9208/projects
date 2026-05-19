import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
from core.spark import get_spark_api, get_spark_local


def run():
    spark = get_spark_api() if settings.use_gcs else get_spark_local()
    spark.sparkContext.setLogLevel("ERROR")

    silver_path = f"{settings.effective_silver_path}/subway"

    df = spark.read.format("delta").load(silver_path)
    before = df.count()
    print(f"중복 제거 전: {before:,} rows")

    df_dedup = df.dropDuplicates(["use_ymd", "line_num", "subway_sta_nm"])
    after = df_dedup.count()
    print(f"중복 제거 후: {after:,} rows (제거: {before - after:,})")

    df_dedup.write.format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .partitionBy("use_ymd") \
        .save(silver_path)

    print("Silver 테이블 중복 제거 완료")
    spark.stop()


if __name__ == "__main__":
    run()
