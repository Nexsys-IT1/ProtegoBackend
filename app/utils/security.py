# app/core/security.py
from datetime import datetime, timedelta
from http.client import HTTPException

from fastapi import Depends, HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError,jwt
from app.core.config import settings


secret_key = "hgjhgjhjh786fytf6r67"
algorithm = "HS256"
access_token_expire_minutes = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/users")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def verify_access_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    return payload
