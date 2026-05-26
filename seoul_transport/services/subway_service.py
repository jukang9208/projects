from core.config import settings
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


class UsageService:

    def __init__(self, spark: SparkSession):
        self.spark = spark

    def get_daily_usage(self, station: str = None, line: str = None):
      
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_daily_avg")
        if station:
            df = df.filter(F.col("subway_sta_nm") == station)
        if line:
            df = df.filter(F.col("line_num") == line)
        return df.orderBy("line_num", "subway_sta_nm").toPandas().to_dict(orient="records")

    def get_top_stations(self, line: str = None, limit: int = 10):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_daily_avg")
        if line:
            df = df.filter(F.col("line_num") == line)
        return df.orderBy(F.col("avg_ride").desc()).limit(limit).toPandas().to_dict(orient="records")

    def get_weekly_pattern(self, station: str):
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_weekly")
        # avg_ride/avg_alight: F.avg(null) → NaN → json.dumps ValueError 방지
        # day_of_week/is_weekend: IntegerType/BooleanType → numpy.int32 → cast("long") 으로 JSON 직렬화
        return df.filter(F.col("subway_sta_nm") == station) \
                 .select(
                     "line_num", "subway_sta_nm",
                     F.col("day_of_week").cast("long").alias("day_of_week"),
                     F.coalesce(F.col("avg_ride"),   F.lit(0.0)).alias("avg_ride"),
                     F.coalesce(F.col("avg_alight"), F.lit(0.0)).alias("avg_alight"),
                     F.col("is_weekend").cast("long").alias("is_weekend"),
                 ) \
                 .orderBy("day_of_week") \
                 .toPandas().to_dict(orient="records")

    def get_monthly_trend(self, station: str):

        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_monthly")
        return df.filter(F.col("subway_sta_nm") == station) \
                 .orderBy("year_month") \
                 .toPandas().to_dict(orient="records")

    def get_meta(self):
        # 실제 수집 기간과 통계 반환 (spark 집)
        df = self.spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")
        row = df.agg(
            F.date_format(F.min("use_ymd"), "yyyy-MM-dd").alias("min_date"),
            F.date_format(F.max("use_ymd"), "yyyy-MM-dd").alias("max_date"),
            F.countDistinct("use_ymd").alias("total_days"),
            F.countDistinct("subway_sta_nm").alias("total_stations"),
        ).collect()[0]

        # 수집된 월 목록 생성 
        months_df = df.select(
            F.date_format("use_ymd", "yyyy-MM").alias("month")
        ).distinct().orderBy("month")
        months = [r["month"] for r in months_df.collect()]

        return {
            "min_date": row["min_date"],
            "max_date": row["max_date"],
            "total_days": int(row["total_days"]),
            "total_stations": int(row["total_stations"]),
            "available_months": months,
        }

    def get_daily_trend(self, station: str, start_date: str = None, end_date: str = None):
        
        df = self.spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")
        df = df.filter(F.col("subway_sta_nm") == station)
        if start_date:
            df = df.filter(F.col("use_ymd") >= start_date)
        if end_date:
            df = df.filter(F.col("use_ymd") <= end_date)
        # 환승역은 line_num이 여러 개이므로 날짜별 합산
        return df.groupBy("use_ymd").agg(
            F.sum("ride_num").alias("ride_num"),
            F.sum("alight_num").alias("alight_num"),
        ).select(
            F.date_format("use_ymd", "yyyy-MM-dd").alias("date"),
            "ride_num",
            "alight_num",
        ).orderBy("use_ymd") \
         .toPandas().to_dict(orient="records")


class TransferService:
    

    def __init__(self, spark: SparkSession):
        self.spark = spark

    def get_transfer_stations(self):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_stations")
        return df.orderBy(F.col("line_count").desc()) \
                 .toPandas().to_dict(orient="records")

    def get_transfer_pattern(self, station: str):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_pattern")
        return df.filter(F.col("subway_sta_nm") == station) \
                 .orderBy("line_num") \
                 .toPandas().to_dict(orient="records")

    def get_busiest_transfer(self, month: str = None):
        # 환승역 승차량 TOP 10 
        if month:
            df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_monthly")
            df = df.filter(F.col("year_month") == month)
        else:
            df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_pattern")
        return df.groupBy("subway_sta_nm") \
                 .agg(F.sum("total_ride").alias("total_ride")) \
                 .orderBy(F.col("total_ride").desc()) \
                 .limit(10) \
                 .toPandas().to_dict(orient="records")


class HourlyService:
    # 시간대별 혼잡도 

    def __init__(self, spark: SparkSession):
        self.spark = spark

    def get_hourly_pattern(self, station: str, line: str = None, month: str = None) -> list[dict]:
        if month:
            # Silver 시간대 테이블에서 해당 월만 조회 (월 누계 → 일 평균 변환)
            use_mm = month.replace("-", "")   # "2026-05" → "202605"
            df = self.spark.read.format("delta").load(
                f"{settings.effective_silver_path}/subway_hourly"
            )
            df = df.filter(F.col("subway_sta_nm") == station) \
                   .filter(F.col("use_mm") == use_mm)
            if line:
                df = df.filter(F.col("line_num") == line)
            df = df.withColumn(
                "days_in_month",
                F.dayofmonth(F.last_day(
                    F.to_date(F.concat(F.col("use_mm"), F.lit("01")), "yyyyMMdd")
                ))
            )
            return df.groupBy("hour") \
                .agg(
                    F.sum(F.col("ride_num")   / F.col("days_in_month")).alias("avg_ride"),
                    F.sum(F.col("alight_num") / F.col("days_in_month")).alias("avg_alight"),
                    F.max(F.col("ride_num")   / F.col("days_in_month")).alias("max_ride"),
                ) \
                .orderBy("hour") \
                .toPandas().to_dict(orient="records")
        else:
            # Gold 전체 기간 평균 (기본)
            df = self.spark.read.format("delta").load(
                f"{settings.effective_gold_path}/congestion_hourly_avg"
            )
            df = df.filter(F.col("subway_sta_nm") == station)
            if line:
                df = df.filter(F.col("line_num") == line)
            # 환승역은 호선별 합산
            return df.groupBy("hour") \
                .agg(
                    F.sum("avg_ride").alias("avg_ride"),
                    F.sum("avg_alight").alias("avg_alight"),
                    F.sum("max_ride").alias("max_ride"),
                ) \
                .orderBy("hour") \
                .toPandas().to_dict(orient="records")

    def get_peak_hours(self, station: str) -> list[dict]:
        # 역별 피크타임 TOP3 시간대
        df = self.spark.read.format("delta").load(
            f"{settings.effective_gold_path}/congestion_peak_hours"
        )
        return df.filter(F.col("subway_sta_nm") == station) \
            .orderBy(F.col("avg_ride").desc()) \
            .toPandas().to_dict(orient="records")

    def get_rush_hour_ranking(self, hour: int = 8, limit: int = 10) -> list[dict]:
        # 특정 시간대 혼잡역 
        df = self.spark.read.format("delta").load(
            f"{settings.effective_gold_path}/congestion_hourly_avg"
        )
        return df.filter(F.col("hour") == hour) \
            .groupBy("subway_sta_nm") \
            .agg(F.sum("avg_ride").alias("avg_ride")) \
            .orderBy(F.col("avg_ride").desc()) \
            .limit(limit) \
            .toPandas().to_dict(orient="records")

    def get_heatmap(self, line: str = None) -> list[dict]:
        
        df = self.spark.read.format("delta").load(
            f"{settings.effective_gold_path}/congestion_hourly_avg"
        )
        if line:
            df = df.filter(F.col("line_num") == line)
        return df.groupBy("subway_sta_nm", "hour") \
            .agg(F.sum("avg_ride").alias("avg_ride")) \
            .orderBy("subway_sta_nm", "hour") \
            .toPandas().to_dict(orient="records")