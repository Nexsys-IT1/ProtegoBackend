from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import JSONB  
from app.db.base import Base

class ThirdPartyAuth(Base):
    __tablename__ = "third_party_auth"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    base_url = Column(Text, nullable=False)
    auth_url = Column(Text, nullable=False)
    auth_config = Column(MutableDict.as_mutable(JSONB), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            f"<ThirdPartyAuth id={self.id}, name='{self.name}', "
            f"url='{self.base_url}{self.auth_url}'>"
        )
