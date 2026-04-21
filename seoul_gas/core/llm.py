# llm.py
from google import genai
from core.config import GOOGLE_API_KEY
from services.db_service import (
    get_district_stats, 
    get_district_trend, 
    get_district_cluster,
    search_rag_documents,
    get_latest_district_stats,
    get_latest_year_for_district
)

client = genai.Client(api_key=GOOGLE_API_KEY)

tools = [
    get_district_stats, 
    get_district_trend, 
    get_district_cluster,
    search_rag_documents,
    get_latest_district_stats,
    get_latest_year_for_district
]

chat = client.chats.create(
    model="gemini-2.5-flash",
    config={"tools": tools}
)