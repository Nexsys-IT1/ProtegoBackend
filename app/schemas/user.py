# app/schemas/auth.py
from pydantic import BaseModel

class UserRead(BaseModel):
    id: int
    email: str
    name: str | None = None
    is_active: bool

class TokenUser(BaseModel):
    id: int
    email: str
    name: str | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: TokenUser

class UserCreate(BaseModel):
    email: str
    password: str