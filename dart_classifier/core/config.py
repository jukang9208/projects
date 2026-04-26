import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


CLASSIFIER_MODEL_DIR = str(BASE_DIR / "models" / "dart_classifier")

APP_TITLE = "DART 공시 분류기 API"
APP_VERSION = "0.1.0"

LABEL_NAMES = ["감사보고서", "사업보고서", "유상증자"]

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
DART_API_KEY:   str = os.environ["DART_API_KEY"]
GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
EMBEDDING_DIM: int = 768

NAVER_CLIENT_ID:     str = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET: str = os.environ.get("NAVER_CLIENT_SECRET", "")
