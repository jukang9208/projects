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
        return df.orderBy("line_num", "subway_sta_nm") \
                 .toPandas().to_dict(orient="records")

    def get_top_stations(self, line: str = None, limit: int = 10):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_daily_avg")
        if line:
            df = df.filter(F.col("line_num") == line)
        return df.orderBy(F.col("avg_ride").desc()) \
                 .limit(limit) \
                 .toPandas().to_dict(orient="records")

    def get_weekly_pattern(self, station: str):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_weekly")
        return df.filter(F.col("subway_sta_nm") == station) \
                 .orderBy("day_of_week") \
                 .toPandas().to_dict(orient="records")

    def get_monthly_trend(self, station: str):

        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/congestion_monthly")
        return df.filter(F.col("subway_sta_nm") == station) \
                 .orderBy("year_month") \
                 .toPandas().to_dict(orient="records")

    def get_daily_trend(self, station: str, start_date: str = None, end_date: str = None):
        
        df = self.spark.read.format("delta").load(f"{settings.effective_silver_path}/subway")
        df = df.filter(F.col("subway_sta_nm") == station)
        if start_date:
            df = df.filter(F.col("use_ymd") >= start_date)
        if end_date:
            df = df.filter(F.col("use_ymd") <= end_date)
        return df.select(
            F.date_format("use_ymd", "yyyy-MM-dd").alias("date"),
            "line_num",
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

    def get_busiest_transfer(self):
       
        df = self.spark.read.format("delta").load(f"{settings.effective_gold_path}/transfer_pattern")
        return df.groupBy("subway_sta_nm") \
                 .agg(F.sum("total_ride").alias("total_ride")) \
                 .orderBy(F.col("total_ride").desc()) \
                 .limit(10) \
                 .toPandas().to_dict(orient="records")
