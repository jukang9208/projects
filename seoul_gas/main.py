from fastapi import FastAPI
from api.gas_cluster import router as cluster_router
from api.gas_rag import router as rag_router
from api.gas_corr import router as corr_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title = "Seoul Gas Agent API")

origins = ["https://jukang.tech", 
            "http://localhost:3000", 
            "https://jukang-frontend-38796498369.asia-northeast1.run.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           
    allow_credentials=True,          
    allow_methods=["*"],             
    allow_headers=["*"],             
)

app.include_router(cluster_router, prefix="/analysis/seoulgas", tags=["seoulgas-cluster"])
app.include_router(corr_router, prefix="/analysis/seoulgas", tags=["seoulgas-corr"])
app.include_router(rag_router, prefix="/analysis/seoulgas", tags=["seoulgas-rag"])

@app.get("/")

def root():
    return {"status": "ok", "message": "Seoul Gas API Server is running!"}