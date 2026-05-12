"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.routers import auth


app = FastAPI(title="GreenBrain API")


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/")
def root():
    return {"message: Hello GreenBrain"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
