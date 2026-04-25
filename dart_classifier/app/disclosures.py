from schemas.classify import DisclosuresResponse
from fastapi import APIRouter, HTTPException, Query
from services.disclosure import get_classified_disclosures

router = APIRouter(prefix="/disclosures", tags=["공시 자동 조회"])


@router.get("", response_model=DisclosuresResponse)
async def list_disclosures(
    corp_name: str = Query(..., description="기업명 (예: 삼성전자)"),
    count:     int = Query(5,   ge=1, le=20, description="조회할 공시 수"),
):

    try:
        return get_classified_disclosures(corp_name, count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
