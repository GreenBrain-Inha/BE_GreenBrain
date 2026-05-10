"""FastAPI application entrypoint."""

from fastapi import FastAPI


app = FastAPI(title="GreenBrain API")

@app.get("/")
def root() :
    return {"message: Hello GreenBrain"}

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

