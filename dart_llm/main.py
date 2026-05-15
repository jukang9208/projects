from fastapi import FastAPI
from app.router import router
from core.model import get_llm
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_llm()   
    yield


app = FastAPI(title="DART LLM API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jukang.tech", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
