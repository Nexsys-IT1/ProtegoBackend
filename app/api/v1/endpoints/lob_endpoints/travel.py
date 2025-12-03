
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.lob.travel import TravelInsuranceRequest

router = APIRouter()
@router.post('/get-quotes', response_model=str)
async def get_quotes(payload: TravelInsuranceRequest, db: Session = Depends(get_db)):
    return "Quotes data"