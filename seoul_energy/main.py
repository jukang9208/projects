import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.energy_router import router as energy_router
from app.energyrag_router import router as rag_router
from app.analysis_router import router as analysis_router

app = FastAPI(
    title="Seoul Energy API",
    description="서울 자치구별 에너지 데이터 조회 API",
    version="1.0.0",
)

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

@app.get("/")
def read_root():
    return {"message": "Seoul Energy API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(energy_router)
app.include_router(analysis_router)
app.include_router(rag_router)

port = int(os.environ.get("PORT", 8080))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=port)