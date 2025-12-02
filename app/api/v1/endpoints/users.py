from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user import TokenResponse, UserCreate, UserRead
from app.services.user_service import UserService
from app.utils.password import get_password_hash, verify_password
from app.utils.security import create_access_token

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = UserService.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = UserService.create_user(db, payload)
    access_token = create_access_token({"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user  # FastAPI will validate against TokenUser
    }

@router.post('/login', response_model=TokenResponse)
def login_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = UserService.get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Invalid email or password"
        )
    token = create_access_token(data={"sub": user.email})
    response= {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
        }
        }
    return response


@router.get("/user/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user
