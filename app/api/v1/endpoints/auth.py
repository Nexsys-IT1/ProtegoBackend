from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from app.core.config import settings

router = APIRouter()

# Placeholder - implement JWT auth when ready
@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    raise HTTPException(501, "Not implemented - replace with JWT auth implementation")
