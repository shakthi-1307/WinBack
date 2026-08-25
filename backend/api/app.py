"""The API application. Wiring only — no business logic lives here.

    uvicorn backend.api.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import campaign, guardrails, metrics, transactions
from backend.config.mode import fake_gateway_permitted, razorpay_configured
from backend.config.status import gateway_is_live, model_is_live

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Winback", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaign.router)
app.include_router(transactions.router)
app.include_router(metrics.router)
app.include_router(guardrails.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model": "live" if model_is_live() else "offline scripted stand-in",
        "gateway": "live razorpay test mode" if gateway_is_live() else "test double",
        "gateway_is_real": razorpay_configured(),
        "strict": not fake_gateway_permitted(),
    }


if FRONTEND_DIR.exists():
    app.mount("/styles", StaticFiles(directory=FRONTEND_DIR / "styles"), name="styles")
    app.mount("/scripts", StaticFiles(directory=FRONTEND_DIR / "scripts"), name="scripts")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
