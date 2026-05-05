from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.subway_router import router as subway_router

app = FastAPI(
    title="Seoul Subway Lakehouse API",
    description="서울시 지하철 승하차 데이터 분석 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jukang.tech",
        "http://localhost:3000",
        "https://jukang-frontend-38796498369.asia-northeast1.run.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(subway_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
