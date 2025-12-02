from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title="FastAPI Scalable App")
Base.metadata.create_all(bind=engine)
app.include_router(api_router, prefix="/api/v1")

