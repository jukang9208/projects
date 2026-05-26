from core.config import settings
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType

# 시간대별 컬럼 (4~23시)
_HOURS = list(range(4, 24))


def raw_to_silver(spark: SparkSession, date: str):
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

    from delta.tables import DeltaTable

    if DeltaTable.isDeltaTable(spark, silver_path):
        # 재실행 시 중복 방지 (MERGE)
        DeltaTable.forPath(spark, silver_path).alias("t").merge(
            df_clean.alias("n"),
            "t.use_ymd = n.use_ymd AND t.line_num = n.line_num AND t.subway_sta_nm = n.subway_sta_nm"
        ).whenNotMatchedInsertAll().execute()
    else:
        df_clean.write.format("delta") \
            .mode("overwrite") \
            .partitionBy("use_ymd") \
            .save(silver_path)

    print(f"[raw_to_silver] 완료 → {silver_path} ({df_clean.count()} rows)")


def silver_to_gold_congestion(spark: SparkSession):
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

    # 역별·요일별 평균
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

    transfer_names = [r["subway_sta_nm"] for r in df_transfer.collect()]
    df_filtered = df.filter(F.col("subway_sta_nm").isin(transfer_names))

    df_filtered \
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

    # 환승역 월별 집계 (프론트 월별 필터용)
    df_filtered \
        .withColumn("year_month", F.date_format("use_ymd", "yyyy-MM")) \
        .groupBy("subway_sta_nm", "year_month") \
        .agg(F.sum("ride_num").alias("total_ride")) \
        .write.format("delta").mode("overwrite") \
        .save(f"{settings.effective_gold_path}/transfer_monthly")
    print("[silver_to_gold] transfer_monthly 완료")


def silver_to_gold_incremental(spark: SparkSession, date: str):
    # 하루치 Silver → Gold 증분 반영 (Delta MERGE)
    from delta.tables import DeltaTable
    from datetime import datetime as _dt

    use_date   = _dt.strptime(date, "%Y%m%d").date()
    year_month = date[:4] + "-" + date[4:6]
    gold   = settings.effective_gold_path
    silver = f"{settings.effective_silver_path}/subway"

    df_day = spark.read.format("delta").load(silver) \
        .filter(F.col("use_ymd") == use_date)

    if df_day.rdd.isEmpty():
        print(f"[SKIP] {date} - Silver 데이터 없음")
        return

    # 1. congestion_daily_avg (가중 평균)
    day_agg = df_day.groupBy("line_num", "subway_sta_nm").agg(
        F.avg("ride_num").alias("day_avg_ride"),
        F.avg("alight_num").alias("day_avg_alight"),
        F.max("ride_num").alias("day_max_ride"),
        F.max("alight_num").alias("day_max_alight"),
    )
    path_da = f"{gold}/congestion_daily_avg"
    if DeltaTable.isDeltaTable(spark, path_da):
        DeltaTable.forPath(spark, path_da).alias("t").merge(
            day_agg.alias("n"),
            "t.line_num = n.line_num AND t.subway_sta_nm = n.subway_sta_nm"
        ).whenMatchedUpdate(set={
            "avg_ride":   "CASE WHEN n.day_avg_ride IS NOT NULL THEN (t.avg_ride * t.data_days + n.day_avg_ride) / (t.data_days + 1) ELSE t.avg_ride END",
            "avg_alight": "CASE WHEN n.day_avg_alight IS NOT NULL THEN (t.avg_alight * t.data_days + n.day_avg_alight) / (t.data_days + 1) ELSE t.avg_alight END",
            "max_ride":   "CASE WHEN n.day_max_ride IS NOT NULL THEN greatest(t.max_ride, n.day_max_ride) ELSE t.max_ride END",
            "max_alight": "CASE WHEN n.day_max_alight IS NOT NULL THEN greatest(t.max_alight, n.day_max_alight) ELSE t.max_alight END",
            "data_days":  "CASE WHEN n.day_avg_ride IS NOT NULL THEN t.data_days + 1 ELSE t.data_days END",
        }).whenNotMatchedInsert(values={
            "line_num":      "n.line_num",
            "subway_sta_nm": "n.subway_sta_nm",
            "avg_ride":      "n.day_avg_ride",
            "avg_alight":    "n.day_avg_alight",
            "max_ride":      "n.day_max_ride",
            "max_alight":    "n.day_max_alight",
            "data_days":     F.lit(1).cast(LongType()),
        }).execute()
    else:
        day_agg.withColumnRenamed("day_avg_ride", "avg_ride") \
            .withColumnRenamed("day_avg_alight", "avg_alight") \
            .withColumnRenamed("day_max_ride", "max_ride") \
            .withColumnRenamed("day_max_alight", "max_alight") \
            .withColumn("data_days", F.lit(1).cast(LongType())) \
            .write.format("delta").mode("overwrite").save(path_da)
    print("[incremental] congestion_daily_avg 완료")

    # 2. congestion_weekly (요일별 가중 평균, week_cnt 추적)
    dow_agg = df_day \
        .withColumn("day_of_week", F.dayofweek("use_ymd")) \
        .withColumn("is_weekend", F.when(F.col("day_of_week").isin(1, 7), True).otherwise(False)) \
        .groupBy("line_num", "subway_sta_nm", "day_of_week", "is_weekend").agg(
            F.avg("ride_num").alias("day_avg_ride"),
            F.avg("alight_num").alias("day_avg_alight"),
        )
    path_wk = f"{gold}/congestion_weekly"
    table_exists  = DeltaTable.isDeltaTable(spark, path_wk)
    has_week_cnt  = table_exists and \
        "week_cnt" in spark.read.format("delta").load(path_wk).columns

    if table_exists and has_week_cnt:
        # 정상 증분 MERGE
        # day_avg_ride/alight 가 null(API 미반환)이면 기존 값 유지, week_cnt도 증가 안 함
        DeltaTable.forPath(spark, path_wk).alias("t").merge(
            dow_agg.alias("n"),
            "t.line_num = n.line_num AND t.subway_sta_nm = n.subway_sta_nm "
            "AND t.day_of_week = n.day_of_week"
        ).whenMatchedUpdate(set={
            "avg_ride":   "CASE WHEN n.day_avg_ride IS NOT NULL THEN (t.avg_ride * t.week_cnt + n.day_avg_ride) / (t.week_cnt + 1) ELSE t.avg_ride END",
            "avg_alight": "CASE WHEN n.day_avg_alight IS NOT NULL THEN (t.avg_alight * t.week_cnt + n.day_avg_alight) / (t.week_cnt + 1) ELSE t.avg_alight END",
            "week_cnt":   "CASE WHEN n.day_avg_ride IS NOT NULL THEN t.week_cnt + 1 ELSE t.week_cnt END",
        }).whenNotMatchedInsert(values={
            "line_num":      "n.line_num",
            "subway_sta_nm": "n.subway_sta_nm",
            "day_of_week":   "n.day_of_week",
            "is_weekend":    "n.is_weekend",
            "avg_ride":      "n.day_avg_ride",
            "avg_alight":    "n.day_avg_alight",
            "week_cnt":      F.lit(1).cast(LongType()),
        }).execute()
    elif table_exists and not has_week_cnt:
        # 구형 테이블(week_cnt 없음) → Silver 전체 재계산 (마이그레이션, 1회)
        df_all = spark.read.format("delta").load(silver)
        df_all.withColumn("day_of_week", F.dayofweek("use_ymd")) \
            .withColumn("is_weekend", F.when(F.col("day_of_week").isin(1, 7), True).otherwise(False)) \
            .groupBy("line_num", "subway_sta_nm", "day_of_week", "is_weekend").agg(
                F.avg("ride_num").alias("avg_ride"),
                F.avg("alight_num").alias("avg_alight"),
                F.count("*").alias("week_cnt"),
            ).write.format("delta").mode("overwrite") \
            .option("overwriteSchema", "true") \
            .save(path_wk)
        print("[incremental] congestion_weekly 마이그레이션 완료")
    else:
        # 테이블 없음 → 오늘 하루 데이터로 신규 생성 (daily_avg/monthly와 동일 방식)
        dow_agg.withColumnRenamed("day_avg_ride",   "avg_ride") \
               .withColumnRenamed("day_avg_alight", "avg_alight") \
               .withColumn("week_cnt", F.lit(1).cast(LongType())) \
               .write.format("delta").mode("overwrite").save(path_wk)
        print("[incremental] congestion_weekly 신규 생성 완료")
    print("[incremental] congestion_weekly 완료")

    # 3. congestion_monthly (월별 합계 누적)
    month_agg = df_day.withColumn("year_month", F.lit(year_month)) \
        .groupBy("line_num", "subway_sta_nm", "year_month").agg(
            F.sum("ride_num").alias("total_ride"),
            F.sum("alight_num").alias("total_alight"),
        )
    path_mo = f"{gold}/congestion_monthly"
    if DeltaTable.isDeltaTable(spark, path_mo):
        DeltaTable.forPath(spark, path_mo).alias("t").merge(
            month_agg.alias("n"),
            "t.line_num = n.line_num AND t.subway_sta_nm = n.subway_sta_nm "
            "AND t.year_month = n.year_month"
        ).whenMatchedUpdate(set={
            "total_ride":   "t.total_ride + n.total_ride",
            "total_alight": "t.total_alight + n.total_alight",
        }).whenNotMatchedInsert(values={
            "line_num":      "n.line_num",
            "subway_sta_nm": "n.subway_sta_nm",
            "year_month":    "n.year_month",
            "total_ride":    "n.total_ride",
            "total_alight":  "n.total_alight",
        }).execute()
    else:
        month_agg.write.format("delta").mode("overwrite").save(path_mo)
    print("[incremental] congestion_monthly 완료")

    # 4. transfer tables
    ts_path = f"{gold}/transfer_stations"
    if not DeltaTable.isDeltaTable(spark, ts_path):
        print("[SKIP] transfer_stations 없음 — build_lakehouse.py 먼저 실행 필요")
        return

    transfer_names = [r["subway_sta_nm"] for r in
        spark.read.format("delta").load(ts_path).select("subway_sta_nm").collect()]
    df_day_tr = df_day.filter(F.col("subway_sta_nm").isin(transfer_names))

    if df_day_tr.rdd.isEmpty():
        print("[incremental] 환승역 데이터 없음, skip")
        return

    # transfer_pattern MERGE (tp_cnt 기반 가중 평균)
    tp_agg = df_day_tr.groupBy("subway_sta_nm", "line_num").agg(
        F.avg("ride_num").alias("day_avg_ride"),
        F.avg("alight_num").alias("day_avg_alight"),
        F.sum("ride_num").alias("day_total_ride"),
        F.sum("alight_num").alias("day_total_alight"),
    )
    path_tp = f"{gold}/transfer_pattern"
    has_tp_cnt = DeltaTable.isDeltaTable(spark, path_tp) and \
        "tp_cnt" in spark.read.format("delta").load(path_tp).columns

    if has_tp_cnt:
        DeltaTable.forPath(spark, path_tp).alias("t").merge(
            tp_agg.alias("n"),
            "t.subway_sta_nm = n.subway_sta_nm AND t.line_num = n.line_num"
        ).whenMatchedUpdate(set={
            "avg_ride":     "(t.avg_ride * t.tp_cnt + n.day_avg_ride) / (t.tp_cnt + 1)",
            "avg_alight":   "(t.avg_alight * t.tp_cnt + n.day_avg_alight) / (t.tp_cnt + 1)",
            "total_ride":   "t.total_ride + n.day_total_ride",
            "total_alight": "t.total_alight + n.day_total_alight",
            "tp_cnt":       "t.tp_cnt + 1",
        }).whenNotMatchedInsert(values={
            "subway_sta_nm": "n.subway_sta_nm",
            "line_num":      "n.line_num",
            "avg_ride":      "n.day_avg_ride",
            "avg_alight":    "n.day_avg_alight",
            "total_ride":    "n.day_total_ride",
            "total_alight":  "n.day_total_alight",
            "tp_cnt":        F.lit(1).cast(LongType()),
        }).execute()
    else:
        # tp_cnt 없는 기존 테이블 → Silver 전체로 재계산 (최초 1회)
        df_all = spark.read.format("delta").load(silver)
        df_all_tr = df_all.filter(F.col("subway_sta_nm").isin(transfer_names))
        df_all_tr.groupBy("subway_sta_nm", "line_num").agg(
            F.avg("ride_num").alias("avg_ride"),
            F.avg("alight_num").alias("avg_alight"),
            F.sum("ride_num").alias("total_ride"),
            F.sum("alight_num").alias("total_alight"),
            F.count("*").alias("tp_cnt"),
        ).write.format("delta").mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(path_tp)
        print("[incremental] transfer_pattern tp_cnt 마이그레이션 완료")
    print("[incremental] transfer_pattern 완료")

    # transfer_monthly MERGE
    tm_agg = df_day_tr.withColumn("year_month", F.lit(year_month)) \
        .groupBy("subway_sta_nm", "year_month").agg(
            F.sum("ride_num").alias("total_ride"),
        )
    path_tm = f"{gold}/transfer_monthly"
    if DeltaTable.isDeltaTable(spark, path_tm):
        DeltaTable.forPath(spark, path_tm).alias("t").merge(
            tm_agg.alias("n"),
            "t.subway_sta_nm = n.subway_sta_nm AND t.year_month = n.year_month"
        ).whenMatchedUpdate(set={
            "total_ride": "t.total_ride + n.total_ride",
        }).whenNotMatchedInsert(values={
            "subway_sta_nm": "n.subway_sta_nm",
            "year_month":    "n.year_month",
            "total_ride":    "n.total_ride",
        }).execute()
    else:
        tm_agg.write.format("delta").mode("overwrite").save(path_tm)
    print("[incremental] transfer_monthly 완료")
    print(f"[incremental] {date} Gold 증분 업데이트 완료 ✓")


def hourly_raw_to_silver(spark: SparkSession, month: str):
    # Wide CSV(역당 1행) → Silver Long 포맷(역당 20행, 4~23시)
    raw_path    = f"{settings.effective_raw_path}/subway_hourly/subway_hourly_{month}.csv"
    silver_path = f"{settings.effective_silver_path}/subway_hourly"

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

    from delta.tables import DeltaTable

    if DeltaTable.isDeltaTable(spark, silver_path):
        DeltaTable.forPath(spark, silver_path).alias("t").merge(
            df_long.alias("n"),
            "t.use_mm = n.use_mm AND t.line_num = n.line_num "
            "AND t.subway_sta_nm = n.subway_sta_nm AND t.hour = n.hour"
        ).whenNotMatchedInsertAll().execute()
    else:
        df_long.write.format("delta") \
            .mode("overwrite") \
            .partitionBy("use_mm") \
            .save(silver_path)

    print(f"[hourly_raw_to_silver] {month} 완료 → {silver_path} ({df_long.count()} rows)")


def silver_to_gold_hourly(spark: SparkSession):
    silver_path = f"{settings.effective_silver_path}/subway_hourly"
    gold_path   = settings.effective_gold_path

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
        .save(f"{gold_path}/congestion_hourly_avg")
    print("[silver_to_gold_hourly] congestion_hourly_avg 완료")

    # 역별 피크타임 (평균 승차 기준 상위 3시간대)
    from pyspark.sql.window import Window
    w = Window.partitionBy("subway_sta_nm").orderBy(F.col("avg_ride").desc())

    df_hourly = spark.read.format("delta").load(f"{gold_path}/congestion_hourly_avg")
    df_hourly \
        .groupBy("subway_sta_nm", "hour") \
        .agg(F.avg("avg_ride").alias("avg_ride")) \
        .withColumn("rank", F.rank().over(w)) \
        .filter(F.col("rank") <= 3) \
        .drop("rank") \
        .write.format("delta").mode("overwrite") \
        .save(f"{gold_path}/congestion_peak_hours")
    print("[silver_to_gold_hourly] congestion_peak_hours 완료")
