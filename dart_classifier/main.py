import sys
import torch
from fastapi import FastAPI
from app import classify, rag
from core.config import APP_TITLE, APP_VERSION
from fastapi.middleware.cors import CORSMiddleware

print(f"Python Version: {sys.version}")
print(f"Torch Version: {torch.__version__}")
print(f"Device check: {'CPU' if not torch.cuda.is_available() else 'GPU'}")

app = FastAPI(title=APP_TITLE, version=APP_VERSION)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "https://jukang.tech",
    "http://localhost:3000",
    "https://jukang-frontend-38796498369.asia-northeast1.run.app/", 
    ],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(classify.router)
app.include_router(rag.router)

@app.get("/")
async def root():
    return {"title": APP_TITLE, "version": APP_VERSION, "status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
