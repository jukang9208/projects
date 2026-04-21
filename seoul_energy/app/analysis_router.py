from db.session import get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query, HTTPException
from services.analysis_service import (
    get_optimal_k,
    get_elbow_data,
    get_kmeans_clusters,
    clear_analysis_cache,
    get_silhouette_scores,
    get_correlation_matrix
)

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"]
)

@router.get("/correlation")
def correlation(db: Session = Depends(get_db)):
    result = get_correlation_matrix(db)

    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/elbow")
def elbow(
    start_k: int = Query(2, ge=2, le=10),
    end_k: int = Query(8, ge=2, le=10),
    db: Session = Depends(get_db),
):
    result = get_elbow_data(db, (start_k, end_k))

    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/silhouette")
def silhouette(
    start_k: int = Query(2, ge=2, le=10),
    end_k: int = Query(8, ge=2, le=10),
    db: Session = Depends(get_db),
):
    
    result = get_silhouette_scores(db, (start_k, end_k))

    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/kmeans")
def kmeans(
    k: int = Query(4, ge=2, le=8),
    db: Session = Depends(get_db)
):
    result = get_kmeans_clusters(db, k)
    
    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/optimal-k")
def optimal_k(
    start_k: int = Query(2, ge=2, le=10),
    end_k: int = Query(8, ge=2, le=10),
    db: Session = Depends(get_db),
):
    result = get_optimal_k(db, (start_k, end_k))

    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result
        

@router.post("/cache/clear")
def clear_cache():
    clear_analysis_cache()
    return {"message": "analysis cache cleared"}