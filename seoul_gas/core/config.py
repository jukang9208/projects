import os
from google import genai  # 최신 SDK 임포트 방식
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("supabase_URL")
SUPABASE_KEY = os.getenv("supabase_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    raise ValueError("환경변수 누락")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)