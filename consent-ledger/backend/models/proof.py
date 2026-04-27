"""
models/proof.py — Pydantic v2 models for ZK proof operations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────── Proof generation request models ──────────────────


class AgeRangeProofRequest(BaseModel):
    """Request body for POST /proof/age-range."""

    secret_age: int = Field(..., ge=0, le=150, description="User's actual age (never stored).")
    salt: int = Field(..., description="Random integer salt for commitment binding.")
    min_age: int = Field(default=18, ge=0)
    max_age: int = Field(default=120, le=200)


class ConsentCommitmentProofRequest(BaseModel):
    """Request body for POST /proof/consent-commitment."""

    data_type: str = Field(
        ...,
        description="Plain-text data type, e.g. 'medical_records' (never stored).",
    )
    purpose: str = Field(
        ...,
        description="Plain-text purpose, e.g. 'annual health screening' (never stored).",
    )
    salt: int = Field(..., description="Random integer salt.")
    requester_id: str = Field(
        ...,
        description="Algorand address of the requesting organisation.",
    )


class NullifierProofRequest(BaseModel):
    """Request body for POST /proof/nullifier."""

    identity_secret: str = Field(
        ...,
        description="Hex-encoded HMAC(aadhaar_number, app_secret). Never stores raw Aadhaar.",
    )
    consent_id: int = Field(..., description="Numeric consent identifier.")
    consent_hash: str = Field(
        ...,
        description="Hex-encoded commitment already stored on-chain.",
    )


# ──────────────────────── Proof response models ────────────────────────────


class ProofResponse(BaseModel):
    """Generic proof response returned by all /proof/* generation endpoints."""

    circuit: str = Field(..., description="One of: age_range, consent_commitment, nullifier.")
    proof_hash: str = Field(
        ...,
        description="Hex-encoded SHA-256 of the raw proof bytes. Submit to ZKVerifier on-chain.",
    )
    commitment: str | None = Field(
        default=None,
        description="Hex-encoded 32-byte Poseidon commitment (age_range / consent_commitment circuits).",
    )
    nullifier: str | None = Field(
        default=None,
        description="Hex-encoded 32-byte nullifier (nullifier circuit).",
    )
    public_inputs: dict[str, Any] = Field(default_factory=dict)
    is_simulation: bool = Field(
        default=False,
        description="True when the gnark binary is unavailable and SHA-256 is used instead.",
    )


# ──────────────────────── On-chain submission models ───────────────────────


class SubmitProofOnChainRequest(BaseModel):
    """Request body for POST /proof/submit-on-chain."""

    sender: str = Field(..., description="Algorand address of the user submitting the proof.")
    proof_hash: str = Field(..., min_length=64, max_length=64, description="Hex-encoded 32-byte SHA-256 of proof.")
    circuit_type: int = Field(
        ...,
        ge=0,
        le=2,
        description="0=age_range, 1=consent_commitment, 2=nullifier.",
    )
    consent_app_id: int = Field(default=0, description="ConsentLedger app ID (0 to use configured default).")


class SubmitProofOnChainResponse(BaseModel):
    unsigned_txn_b64: str = Field(
        ...,
        description="Base64 msgpack unsigned ApplicationCallTxn for the user to sign.",
    )


class VerifyBackendRequest(BaseModel):
    """Request body for POST /proof/verify-backend (deployer-only call)."""

    user: str = Field(..., description="Algorand address of the user who submitted the proof.")
    proof_hash: str = Field(..., min_length=64, max_length=64)
    proof_json: dict[str, Any] = Field(
        ...,
        description="Full proof JSON returned by the gnark prover (verify off-chain).",
    )
    circuit: str = Field(..., description="Circuit name: age_range | consent_commitment | nullifier.")


class VerifyBackendResponse(BaseModel):
    gnark_valid: bool
    tx_id: str = Field(default="", description="confirm_verification tx ID if gnark_valid is True.")
    message: str = ""
