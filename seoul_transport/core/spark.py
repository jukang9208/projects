import os
import sys
import socket
import subprocess

# 모듈 로드 시점에 환경 정리 
# 시스템 Spark 3.2.1 vs pip PySpark 3.5.0 충돌 방지
if "SPARK_HOME" in os.environ:
    _old = os.path.join(os.environ["SPARK_HOME"], "python")
    sys.path = [p for p in sys.path if _old not in p]
    del os.environ["SPARK_HOME"]

# Windows: Java 17 경로 자동 설정
if sys.platform == "win32":
    _result = subprocess.run(["where.exe", "java"], capture_output=True, text=True)
    if _result.stdout.strip():
        _java_exe = _result.stdout.strip().split("\n")[0].strip()
        os.environ["JAVA_HOME"] = str(os.path.dirname(os.path.dirname(_java_exe)))

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from core.config import settings


# GCS connector JAR 
_GCS_CONNECTOR_JAR = "https://storage.googleapis.com/hadoop-lib/gcs/gcs-connector-hadoop3-latest.jar"

_DELTA_EXTENSIONS = {
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
}


def _apply_gcs_config(builder, use_key_file: bool = False):
   
    builder = builder \
        .config("spark.jars", _GCS_CONNECTOR_JAR) \
        .config("spark.hadoop.fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem") \
        .config("spark.hadoop.fs.AbstractFileSystem.gs.impl",
                "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFS") \
        .config("spark.hadoop.google.cloud.auth.service.account.enable", "true")

    if use_key_file:
        # 로컬 개발: 서비스 계정 JSON 키 파일
        from core.config import settings
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            builder = builder.config(
                "spark.hadoop.google.cloud.auth.service.account.json.keyfile",
                settings.GOOGLE_APPLICATION_CREDENTIALS
            )
    # GCP 환경
    return builder


def get_spark_api() -> SparkSession:
   
    if sys.platform == "win32":
        local_ip = socket.gethostbyname(socket.gethostname())
        os.environ["SPARK_LOCAL_IP"] = local_ip
        os.environ["HADOOP_HOME"] = "C:\\hadoop"
        os.environ["PATH"] = os.environ["PATH"] + ";C:\\hadoop\\bin"
        builder = SparkSession.builder \
            .appName(settings.SPARK_APP_NAME) \
            .master("local[1]") \
            .config("spark.driver.host", local_ip) \
            .config("spark.driver.bindAddress", local_ip) \
            .config("spark.ui.enabled", "false")
        if settings.use_gcs:
            builder = _apply_gcs_config(builder, use_key_file=True)
    else:
        builder = SparkSession.builder \
            .appName(settings.SPARK_APP_NAME) \
            .master(settings.SPARK_MASTER)
        if settings.use_gcs:
            builder = _apply_gcs_config(builder, use_key_file=False)  # GCP: Workload Identity

    for k, v in _DELTA_EXTENSIONS.items():
        builder = builder.config(k, v)

    return configure_spark_with_delta_pip(builder).getOrCreate()


def get_spark_local() -> SparkSession:
   
    local_ip = socket.gethostbyname(socket.gethostname())
    os.environ["SPARK_LOCAL_IP"] = local_ip
    os.environ["HADOOP_HOME"] = "C:\\hadoop"
    os.environ["PATH"] = os.environ["PATH"] + ";C:\\hadoop\\bin"

    builder = SparkSession.builder \
        .appName(settings.SPARK_APP_NAME) \
        .master("local[1]") \
        .config("spark.driver.host", local_ip) \
        .config("spark.driver.bindAddress", local_ip) \
        .config("spark.ui.enabled", "false")

    if settings.use_gcs:
        builder = _apply_gcs_config(builder, use_key_file=True)

    for k, v in _DELTA_EXTENSIONS.items():
        builder = builder.config(k, v)

    return configure_spark_with_delta_pip(builder).getOrCreate()
