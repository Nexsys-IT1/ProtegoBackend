
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v1.endpoints.third_party.travel.rak import get_rak_quotes
from app.db.session import get_db
from app.schemas.lob.travel import TravelInsuranceRequest
from app.utils.sse import sse_parallel

router = APIRouter()
@router.post('/get-quotes', response_model=str)
async def get_quotes(payload: TravelInsuranceRequest, db: Session = Depends(get_db)):
    func_list = [{"name": "rak", "func": get_rak_quotes(payload, db)}]
    response = await sse_parallel(func_list)
    return "Quotes data"