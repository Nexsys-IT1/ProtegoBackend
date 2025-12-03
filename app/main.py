from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed_third_party_providers
from app.db.session import SessionLocal, engine

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_third_party_providers(db)
    finally:
        db.close()

    yield
    
app = FastAPI(title="Protego App",lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")

