"""VERIFRAME FastAPI application entry point.

Run (from backend/):  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db
from app.services.provenance.keys import load_keys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("veriframe")

TAGS = [
    {"name": "system", "description": "Health and public configuration"},
    {"name": "dashboard", "description": "Statistics computed from stored records"},
    {"name": "analysis", "description": "AI media-forensics analysis (plus independent provenance inspection)"},
    {"name": "provenance", "description": "C2PA signing/verification and the detached Ed25519 educational envelope"},
    {"name": "integrity-lab", "description": "Guided tamper demonstration using real cryptographic verification"},
    {"name": "cases", "description": "Durable cases, reports and stored files"},
    {"name": "activity", "description": "Audit log"},
    {"name": "model", "description": "Model card information and held-out metrics"},
    {"name": "demo", "description": "Demo Workspace samples (documented labels)"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_keys()  # generates development keys on first run (keys/ is git-ignored)

    def _warm():
        from app.services.ai.detector import get_detector
        from app.services.ai.faces import get_detector as get_face

        get_detector().info()
        get_face()

    threading.Thread(target=_warm, daemon=True).start()
    logger.info("VERIFRAME API ready; CORS origins: %s", settings.cors_origins)
    yield


app = FastAPI(
    title="VERIFRAME API",
    version=settings.app_version,
    description="Media Authenticity Intelligence — AI media-forensics signals and cryptographic provenance (C2PA) "
                "verification, kept as separate evidence dimensions. Local academic demonstration (ISC, Team 16).",
    openapi_tags=TAGS,
    lifespan=lifespan,
)

# Development CORS: only the local Vite origin(s) may call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": {"code": "VALIDATION_ERROR", "message": "Invalid request.",
                                                             "errors": [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]}})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # pragma: no cover - safety net
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "An internal error occurred. It has been logged."}})


app.include_router(router)
