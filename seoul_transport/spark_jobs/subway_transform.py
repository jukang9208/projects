from core.config import settings
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType


# Raw → Silver
def raw_to_silver(spark: SparkSession, date: str):
    # GCS 사용 시: gs://버킷명/raw/subway/YYYYMM/subway_YYYYMMDD.csv
    # 로컬 사용 시: data/raw/subway/YYYYMM/subway_YYYYMMDD.csv
    raw_path    = f"{settings.effective_raw_path}/subway/{date[:6]}/subway_{date}.csv"
    silver_path = f"{settings.effective_silver_path}/subway"

    df = spark.read.csv(raw_path, header=True, inferSchema=True)

    df_clean = df.select(
        F.to_date(F.col("USE_YMD"), "yyyyMMdd").alias("use_ymd"),
        F.col("SBWY_ROUT_LN_NM").alias("line_num"),
        F.col("SBWY_STNS_NM").alias("subway_sta_nm"),
        F.col("GTON_TNOPE").cast(LongType()).alias("ride_num"),
        F.col("GTOFF_TNOPE").cast(LongType()).alias("alight_num"),
    ) \
        .dropna(subset=["use_ymd", "line_num", "subway_sta_nm"]) \
        .dropDuplicates(["use_ymd", "line_num", "subway_sta_nm"])

    df_clean.write.format("delta") \
        .mode("append") \
        .partitionBy("use_ymd") \
        .save(silver_path)

    print(f"[raw_to_silver] 완료 → {silver_path} ({df_clean.count()} rows)")


# Silver → Gold
def silver_to_gold_congestion(spark: SparkSession):
    """일별 이용량 기반 Gold 테이블 생성"""
    df = spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")

    # 역별 평균 일 승하차
    df.groupBy("line_num", "subway_sta_nm") \
        .agg(
            F.avg("ride_num").alias("avg_ride"),
            F.avg("alight_num").alias("avg_alight"),
            F.max("ride_num").alias("max_ride"),
            F.max("alight_num").alias("max_alight"),
            F.count("use_ymd").alias("data_days"),
        ) \
        .write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/congestion_daily_avg")
    print("[silver_to_gold] congestion_daily_avg 완료")

    # 역별·요일별 평균 (평일 vs 주말)
    df.withColumn("day_of_week", F.dayofweek("use_ymd")) \
        .withColumn("is_weekend", F.when(F.col("day_of_week").isin(1, 7), True).otherwise(False)) \
        .groupBy("line_num", "subway_sta_nm", "day_of_week", "is_weekend") \
        .agg(
            F.avg("ride_num").alias("avg_ride"),
            F.avg("alight_num").alias("avg_alight"),
        ) \
        .write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/congestion_weekly")
    print("[silver_to_gold] congestion_weekly 완료")

    # 역별·월별 집계
    df.withColumn("year_month", F.date_format("use_ymd", "yyyy-MM")) \
        .groupBy("line_num", "subway_sta_nm", "year_month") \
        .agg(
            F.sum("ride_num").alias("total_ride"),
            F.sum("alight_num").alias("total_alight"),
        ) \
        .write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/congestion_monthly")
    print("[silver_to_gold] congestion_monthly 완료")


def silver_to_gold_transfer(spark: SparkSession):

    df = spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")

    # 동일 역명이 2개 이상 호선에 등장 → 환승역
    df_transfer = df.groupBy("subway_sta_nm") \
        .agg(F.countDistinct("line_num").alias("line_count")) \
        .filter(F.col("line_count") >= 2)

    df_transfer.write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/transfer_stations")
    print("[silver_to_gold] transfer_stations 완료")

    # 환승역별·호선별 이용 패턴
    transfer_names = [r["subway_sta_nm"] for r in df_transfer.collect()]
    df.filter(F.col("subway_sta_nm").isin(transfer_names)) \
        .groupBy("subway_sta_nm", "line_num") \
        .agg(
            F.avg("ride_num").alias("avg_ride"),
            F.avg("alight_num").alias("avg_alight"),
            F.sum("ride_num").alias("total_ride"),
            F.sum("alight_num").alias("total_alight"),
        ) \
        .write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/transfer_pattern")
    print("[silver_to_gold] transfer_pattern 완료")
