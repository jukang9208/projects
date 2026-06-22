import logging
from fastapi import FastAPI
from api.analyze import router as analyze_router
from api.compare import router as compare_router
from fastapi.middleware.cors import CORSMiddleware

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Jukang.tech Stock Analyzer")

# CORS 설정
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

# 헬스 체크
@app.get("/")
async def root():
    return {"title": "Jukang.tech Stock Analyzer", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

# API 라우터 등록
app.include_router(analyze_router, prefix="/api", tags=["analyze"])
app.include_router(compare_router, prefix="/api", tags=["compare"])
