from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.lob.travel import TravelInsuranceRequest
from app.api.v1.endpoints.third_party.travel.rak import get_rak_quotes
from app.api.v1.endpoints.third_party.travel.gig import get_gig_quotes
from app.utils.sse import sse_parallel
import json

router = APIRouter()

@router.post("/get-quotes")
async def get_quotes(payload: TravelInsuranceRequest, db: Session = Depends(get_db)):
    async def rak_job():
        result =  get_rak_quotes(payload, db)
        print("\n====== RAK QUOTES START ======")
        print(json.dumps(result, indent=2))
        print("=====================================\n")
        return result
    
    async def gig_job():
        result =  get_gig_quotes(payload, db)
        print("\n====== GIG QUOTES SINGLE EVENT ======")
        print(json.dumps(result, indent=2))
        print("=====================================\n")
        return result

    func_list = [
        {
            "name": "rak",   
            "func": rak_job
        },
        {
            "name": "gig",   
            "func": gig_job
        }
    ]

    return await sse_parallel(func_list)
