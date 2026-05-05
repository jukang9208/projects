from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 서울 열린데이터광장 API
    SEOUL_API_KEY: str = ""

    # 국토교통부 TAGO API
    TAGO_API_KEY: str = ""

    # GCS 설정
    GCS_BUCKET_NAME: str = ""
    GCS_PROJECT_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # 로컬: 서비스 계정 JSON 경로 / GCP: 자동 (Workload Identity)

    # Spark 설정
    SPARK_MASTER: str = "local[*]"
    SPARK_APP_NAME: str = "seoul_transport_lakehouse"

    # Delta Lake 경로
    # 로컬: "data/raw" / GCS: "gs://<버킷명>/raw"
    RAW_PATH: str = "data/raw"
    SILVER_PATH: str = "data/silver"
    GOLD_PATH: str = "data/gold"

    @property
    def use_gcs(self) -> bool:
        return bool(self.GCS_BUCKET_NAME)

    @property
    def gcs_raw_path(self) -> str:
        return f"gs://{self.GCS_BUCKET_NAME}/raw"

    @property
    def gcs_silver_path(self) -> str:
        return f"gs://{self.GCS_BUCKET_NAME}/silver"

    @property
    def gcs_gold_path(self) -> str:
        return f"gs://{self.GCS_BUCKET_NAME}/gold"

    @property
    def effective_raw_path(self) -> str:
        return self.gcs_raw_path if self.use_gcs else self.RAW_PATH

    @property
    def effective_silver_path(self) -> str:
        return self.gcs_silver_path if self.use_gcs else self.SILVER_PATH

    @property
    def effective_gold_path(self) -> str:
        return self.gcs_gold_path if self.use_gcs else self.GOLD_PATH

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
