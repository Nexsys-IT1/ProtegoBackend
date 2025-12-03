from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # App security
    SECRET_KEY: str = "changeme"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # RAK Insurance
    RAK_USER_NAME: str
    RAK_PASSWORD: str

    # Gulf Insurance
    GULF_CLIENT_ID: str
    GULF_CLIENT_SECRET: str

    # Liva Insurance
    LIVA_CLIENT_ID: str
    LIVA_CLIENT_SECRET: str
    LIVA_SCOPE: str
    LIVA_LOCATION: str
    LIVA_AUTHKEY: str
    LIVA_LANGUAGE: str
    LIVA_PARTNERID: str
    LIVA_SUBSCRIPTIONKEY: str

    class Config:
        env_file = ".env"

# Instantiate settings
settings = Settings()
