from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.travel import TravelInsuranceRequest
from app.api.v1.endpoints.third_party.travel.rak import get_rak_quotes
from app.utils.sse import sse_parallel

router = APIRouter()

@router.post("/get-quotes")
async def get_quotes(payload: TravelInsuranceRequest, db: Session = Depends(get_db)):
    async def rak_job():
        return get_rak_quotes(payload, db)

    func_list = [
        {
            "name": "rak",   
            "func": rak_job
        }
    ]

    return await sse_parallel(func_list)
