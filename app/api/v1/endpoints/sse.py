
from fastapi import APIRouter


router = APIRouter()
@router.post('/get-quotes', response_model=str)
async def get_quotes():
    pass