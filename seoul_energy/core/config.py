from google import genai
from typing import Optional
from supabase import create_client, Client
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL : str
    supabase_URL : str
    supabase_KEY : str
    GOOGLE_API_KEY : str 

    model_config = SettingsConfigDict(
        env_file = ".env",
        extra = "ignore"
    )

Settings = Settings()

supabase : Client = create_client(Settings.supabase_URL, Settings.supabase_KEY)
genai_client = genai.Client(api_key = Settings.GOOGLE_API_KEY)