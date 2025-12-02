from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _truncate(password: str) -> str:
    return password[:72]

def get_password_hash(password: str):
    return pwd_context.hash(_truncate(password))

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(_truncate(plain_password), hashed_password)
