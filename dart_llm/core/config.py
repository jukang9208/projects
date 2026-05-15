from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    
    DART_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    HF_TOKEN: str = ""
    HF_REPO_ID: str = ""  

    # 파인튜닝 설정
    BASE_MODEL: str = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
    LORA_OUTPUT_DIR: str = "outputs/lora"
    MERGED_OUTPUT_DIR: str = "outputs/merged"

    # 데이터 경로
    RAW_DATA_DIR: str = "data/raw"
    PROCESSED_DATA_DIR: str = "data/processed"
    DATASET_PATH: str = "data/processed/dart_qa_dataset.jsonl"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
