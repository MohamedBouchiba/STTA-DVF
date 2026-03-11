"""Application FastAPI STTA-DVF."""

import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from src.db import get_engine
from src.app.models.adjustments import get_default_coefficients
from src.api.schemas import EstimationRequest, EstimationResponse, HealthResponse
from src.api.service import process_estimation

load_dotenv()

app = FastAPI(
    title="STTA-DVF API",
    version="1.0.0",
    description="API d'estimation immobiliere basee sur les donnees DVF.",
)

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Ajoute le header X-Process-Time a chaque reponse."""
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start:.3f}"
    return response


@app.get("/", include_in_schema=False)
def root():
    """Redirige vers la documentation Swagger."""
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    """Health check : verifie la connexion DB et PostGIS."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # PostGIS version
            row = conn.execute(text("SELECT PostGIS_Version()")).fetchone()
            postgis_version = row[0] if row else None

            # Transactions count
            row = conn.execute(text("SELECT COUNT(*) FROM core.transactions")).fetchone()
            count = row[0] if row else 0

        return HealthResponse(
            status="ok",
            database="connected",
            postgis_version=postgis_version,
            transactions_count=count,
        )
    except Exception as e:
        return HealthResponse(
            status="error",
            database=str(e),
        )


@app.get("/api/v1/defaults")
def defaults():
    """Retourne les coefficients par defaut (pour les sliders admin frontend)."""
    return get_default_coefficients()


@app.post("/api/v1/estimate", response_model=EstimationResponse)
def estimate(request: EstimationRequest):
    """Endpoint principal d'estimation immobiliere."""
    try:
        return process_estimation(request)
    except ValueError as e:
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne: {type(e).__name__}: {e}"},
        )
