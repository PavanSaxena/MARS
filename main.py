from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from app.api.routes import router

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(
    title="MARS Multi-Agent Decision System",
    description="A multi-agent AI system for strategic decision-making across Finance, R&D, Legal, and Operations.",
    version="0.1.0",
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "message": "MARS Decision System is running."}
