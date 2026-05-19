"""FastAPI application entrypoint."""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.routers import auth, challenge_photos, challenges, chat, tokens, users

app = FastAPI(title="GreenBrain API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(challenges.router, prefix="/api/challenges", tags=["challenges"])
app.include_router(challenge_photos.router, prefix="/api/challenge-photos", tags=["challenge-photos"])
app.include_router(tokens.router, prefix="/api/tokens", tags=["tokens"])
app.include_router(users.router, prefix="/api/users", tags=["users"])


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})


@app.get("/")
def root():
    return {"message: Hello GreenBrain"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
