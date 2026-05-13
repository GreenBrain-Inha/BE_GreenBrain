import os
from pydantic_settings import BaseSettings

ENV = os.getenv("APP_ENV", "dev")

def is_dev() -> bool:
    return ENV == "dev"

def access_token_cookie_secure() -> bool:
    return not is_dev()

class Settings(BaseSettings):

    jwt_secret_key: str
    access_token_cookie_secure: bool = True
    open_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

settings = Settings()