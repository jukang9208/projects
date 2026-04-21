from db.session import get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from services.energy_service import (
    get_all_energy_stats,
    get_energy_stats_by_year,
    get_energy_stats_by_district,
)

router = APIRouter(prefix="/energy", tags=["energy"])

@router.get("")
def read_all_energy_stats(db: Session = Depends(get_db)):

    data = get_all_energy_stats(db)
    return {
        "count": len(data),
        "items": data
    }

@router.get("/year/{year}")
def read_energy_stats_by_year(year: int, db: Session = Depends(get_db)):

    data = get_energy_stats_by_year(db, year)

    if not data:
        raise HTTPException(status_code=404, detail=f"{year}년 데이터가 없습니다.")

    return {
        "year": year,
        "count": len(data),
        "items": data
    }

@router.get("/district/{district}") 
def read_energy_stats_by_district(district: str, db: Session = Depends(get_db)):
 
    data = get_energy_stats_by_district(db, district)

    if not data:
        raise HTTPException(
            status_code=404, 
            detail=f"'{district}' 자치구에 해당하는 데이터가 없습니다."
        )

    return {
        "district": district,
        "count": len(data),
        "items": data
    }