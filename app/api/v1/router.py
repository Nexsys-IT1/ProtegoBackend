from fastapi import APIRouter

from .endpoints import users, auth,sse

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sse.router, prefix="/sse", tags=["sse"])

