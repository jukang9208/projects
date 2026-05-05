from airflow import DAG
from datetime import datetime, timedelta
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="seoul_subway_pipeline",
    default_args=default_args,
    description="서울시 지하철 일별 승하차 데이터 파이프라인",
    schedule_interval="0 6 * * *",  # 매일 오전 6시 (전날 데이터 수집)
    start_date=datetime(2026, 4, 1),
    catchup=False,
    tags=["subway", "seoul", "lakehouse"],
) as dag:

    def collect_subway(**context):
        """서울 API → Raw CSV 저장"""
        from ingestion.subway_collector import run
        date = context["ds_nodash"]   # 실행일 기준 전날 날짜 (YYYYMMDD)
        run(date=date)

    def transform_subway(**context):
        """Raw CSV → Silver → Gold 변환"""
        from core.spark import get_spark_api
        from spark_jobs.subway_transform import (
            raw_to_silver,
            silver_to_gold_congestion,
            silver_to_gold_transfer,
        )
        date = context["ds_nodash"]
        spark = get_spark_api()
        raw_to_silver(spark, date)
        silver_to_gold_congestion(spark)
        silver_to_gold_transfer(spark)

    t1_collect   = PythonOperator(task_id="collect_subway",   python_callable=collect_subway)
    t2_transform = PythonOperator(task_id="transform_subway", python_callable=transform_subway)

    t1_collect >> t2_transform  # 수집 완료 후 변환 실행
