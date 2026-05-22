"""FastAPI application entrypoint."""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import auth, challenge_photos, challenges, chat, tokens, users
from app.common.exceptions.handlers import register_exception_handlers

app = FastAPI(title="GreenBrain API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(challenges.router, prefix="/api/challenges", tags=["challenges"])
app.include_router(challenge_photos.router, prefix="/api/challenge-photos", tags=["challenge-photos"])
app.include_router(tokens.router, prefix="/api/tokens", tags=["tokens"])
app.include_router(users.router, prefix="/api/users", tags=["users"])


@app.get("/")
def root():
    return {"message: Hello GreenBrain"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
