"""
main.py — ConsentLedger FastAPI application.

Entry point for the Phase 3 backend service.

Endpoints:
  /auth/digilocker/*      DigiLocker OAuth2 flow
  /proof/*                ZK proof generation & on-chain submission
  /consent/*              Consent grant / revoke / verify (x402 gated)
  /payments/*             x402 payment helpers
  /org/*                  OrgRegistry management

Run locally:
  cd consent-ledger/backend
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers.auth import router as auth_router
from routers.consent import router as consent_router
from routers.payments import org_router, payments_router
from routers.proof import router as proof_router

# ──────────────────────── Logging ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("consent_ledger.backend")


# ──────────────────────── Lifespan ────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ConsentLedger backend starting up.")
    logger.info(
        "Algorand testnet: ConsentLedger=%d  ZKVerifier=%d  OrgRegistry=%d",
        settings.consent_ledger_app_id,
        settings.zk_verifier_app_id,
        settings.org_registry_app_id,
    )
    yield
    logger.info("ConsentLedger backend shutting down.")


# ──────────────────────── App ─────────────────────────────────────────────

app = FastAPI(
    title="ConsentLedger API",
    description=(
        "Decentralized ZK consent management backend for the ConsentLedger dApp. "
        "Implements DigiLocker OAuth, Groth16 ZK proof generation, Algorand contract "
        "interaction, and x402 micropayment gating."
    ),
    version="2.0.0",
    contact={"name": "ConsentLedger", "url": "https://dorahacks.io/buidl/43102"},
    lifespan=lifespan,
)

# ──────────────────────── CORS ────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────── Global exception handler ────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ──────────────────────── Routers ─────────────────────────────────────────

app.include_router(auth_router)
app.include_router(proof_router)
app.include_router(consent_router)
app.include_router(payments_router)
app.include_router(org_router)


# ──────────────────────── Health / info endpoints ─────────────────────────


@app.get("/", tags=["health"], summary="Service info")
async def root():
    return {
        "service": "ConsentLedger Backend",
        "version": "2.0.0",
        "contracts": {
            "consent_ledger": settings.consent_ledger_app_id,
            "zk_verifier": settings.zk_verifier_app_id,
            "org_registry": settings.org_registry_app_id,
        },
        "docs": "/docs",
    }


@app.get("/health", tags=["health"], summary="Health check")
async def health():
    return {"status": "ok"}
