from fastapi import APIRouter
from .endpoints.lob_endpoints import travel
from .endpoints import users, auth

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(travel.router, prefix="/travel", tags=["travel"])

