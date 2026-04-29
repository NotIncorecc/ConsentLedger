"""
routers/proof.py — ZK proof generation and on-chain submission endpoints.

POST /proof/age-range              → generate age_range Groth16 proof
POST /proof/consent-commitment     → generate consent_commitment Groth16 proof
POST /proof/nullifier              → generate nullifier Groth16 proof
POST /proof/submit-on-chain        → build unsigned submit_proof txn for user wallet
POST /proof/verify-backend         → gnark verify + deployer calls confirm_verification
GET  /proof/status                 → check if a proof hash is confirmed on-chain
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from config import settings
from models.proof import (
    AgeRangeProofRequest,
    ConsentCommitmentProofRequest,
    NullifierProofRequest,
    ProofResponse,
    SubmitProofOnChainRequest,
    SubmitProofOnChainResponse,
    VerifyBackendRequest,
    VerifyBackendResponse,
)
from services.algorand import AlgorandService
from services.prover import ProverService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proof", tags=["proof"])

# ──────────────────────── Singletons ──────────────────────────────────────

_prover = ProverService(
    prover_binary=settings.prover_binary,
    keys_dir=settings.prover_keys_dir,
)

_algorand = AlgorandService(
    algod_server=settings.algod_server,
    algod_token=settings.algod_token,
    deployer_mnemonic_phrase=settings.deployer_mnemonic,
    consent_ledger_app_id=settings.consent_ledger_app_id,
    zk_verifier_app_id=settings.zk_verifier_app_id,
    org_registry_app_id=settings.org_registry_app_id,
)

# ──────────────────────── Proof generation endpoints ──────────────────────


@router.post(
    "/age-range",
    response_model=ProofResponse,
    summary="Generate Groth16 age_range proof",
)
async def generate_age_range_proof(req: AgeRangeProofRequest):
    """
    Proves `min_age ≤ secret_age ≤ max_age` without revealing the actual age.

    Returns commitment = Poseidon(secret_age, salt) which should be passed
    to /consent/grant as the `commitment` field.
    """
    result = await _prover.prove_age_range(
        secret_age=req.secret_age,
        salt=req.salt,
        min_age=req.min_age,
        max_age=req.max_age,
    )
    commitment = result.get("public_inputs", {}).get("commitment")
    return ProofResponse(
        circuit="age_range",
        proof_hash=result["proof_hash"],
        commitment=commitment,
        public_inputs=result.get("public_inputs", {}),
        is_simulation=result.get("is_simulation", True),
    )


@router.post(
    "/consent-commitment",
    response_model=ProofResponse,
    summary="Generate Groth16 consent_commitment proof",
)
async def generate_consent_commitment_proof(req: ConsentCommitmentProofRequest):
    """
    Proves knowledge of (data_type, purpose, salt, requester) matching the
    on-chain commitment without revealing any plaintext on-chain.

    Returns commitment = Poseidon(data_type_hash, purpose_hash, salt, requester_id)
    which replaces the plaintext fields in the ConsentLedger contract.
    """
    result = await _prover.prove_consent_commitment(
        data_type=req.data_type,
        purpose=req.purpose,
        salt=req.salt,
        requester_id=req.requester_id,
    )
    commitment = result.get("public_inputs", {}).get("commitment")
    return ProofResponse(
        circuit="consent_commitment",
        proof_hash=result["proof_hash"],
        commitment=commitment,
        public_inputs=result.get("public_inputs", {}),
        is_simulation=result.get("is_simulation", True),
    )


@router.post(
    "/nullifier",
    response_model=ProofResponse,
    summary="Generate Groth16 nullifier proof",
)
async def generate_nullifier_proof(req: NullifierProofRequest):
    """
    Proves SHA256(identity_secret || consent_id) = nullifier for anti-replay.

    The nullifier must be stored on-chain in ConsentRecord. If the same
    (identity_secret, consent_id) is used again the contract will reject it.
    """
    result = await _prover.prove_nullifier(
        identity_secret=req.identity_secret,
        consent_id=req.consent_id,
        consent_hash=req.consent_hash,
    )
    nullifier = result.get("public_inputs", {}).get("nullifier")
    return ProofResponse(
        circuit="nullifier",
        proof_hash=result["proof_hash"],
        nullifier=nullifier,
        public_inputs=result.get("public_inputs", {}),
        is_simulation=result.get("is_simulation", True),
    )


# ──────────────────────── On-chain submission ──────────────────────────────


class SetMembershipRequest(BaseModel):
    field: str
    value: str
    allowed_values: list[str]
    salt: str


class HashEqualityRequest(BaseModel):
    field: str
    value: str
    salt: str


@router.post(
    "/set-membership",
    response_model=ProofResponse,
    summary="Simulate set-membership proof (stub — returns mock commitment)",
)
async def generate_set_membership_proof(req: SetMembershipRequest):
    """
    Stub: proves value ∈ allowed_set without a dedicated gnark circuit.
    Falls back to consent_commitment simulation so the API surface is complete.
    """
    import hashlib, secrets
    proof_hash = hashlib.sha256(f"{req.field}:{req.value}:{req.salt}".encode()).hexdigest()
    commitment = hashlib.sha256(f"commit:{req.field}:{','.join(req.allowed_values)}:{req.salt}".encode()).hexdigest()
    nullifier = secrets.token_hex(32)
    return ProofResponse(
        circuit="set_membership",
        proof_hash=proof_hash,
        commitment=commitment,
        nullifier=nullifier,
        public_inputs={"field": req.field, "allowed_values": req.allowed_values},
        is_simulation=True,
    )


@router.post(
    "/hash-equality",
    response_model=ProofResponse,
    summary="Simulate hash-equality proof (stub — returns mock commitment)",
)
async def generate_hash_equality_proof(req: HashEqualityRequest):
    """
    Stub: proves SHA256(secret_value) = commitment without revealing the value.
    Uses SHA-256 directly as a simulation fallback.
    """
    import hashlib, secrets
    commitment = hashlib.sha256(f"{req.field}:{req.value}:{req.salt}".encode()).hexdigest()
    proof_hash = hashlib.sha256(f"proof:{commitment}".encode()).hexdigest()
    nullifier = secrets.token_hex(32)
    return ProofResponse(
        circuit="hash_equality",
        proof_hash=proof_hash,
        commitment=commitment,
        nullifier=nullifier,
        public_inputs={"field": req.field},
        is_simulation=True,
    )



@router.post(
    "/submit-on-chain",
    response_model=SubmitProofOnChainResponse,
    summary="Build unsigned submit_proof txn for user wallet",
)
async def submit_proof_on_chain(req: SubmitProofOnChainRequest):
    """
    Returns a base64 msgpack unsigned ApplicationCallTxn that the user's wallet
    should sign and submit. This records the proof_hash in ZKVerifierContract so
    the trusted backend can confirm it after off-chain gnark verification.
    """
    consent_app_id = req.consent_app_id or settings.consent_ledger_app_id
    try:
        unsigned_txn_b64 = _algorand.prepare_submit_proof(
            sender=req.sender,
            proof_hash_hex=req.proof_hash,
            circuit_type=req.circuit_type,
            consent_app_id=consent_app_id,
        )
    except Exception as exc:
        logger.error("prepare_submit_proof failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SubmitProofOnChainResponse(unsigned_txn_b64=unsigned_txn_b64)


@router.post(
    "/verify-backend",
    response_model=VerifyBackendResponse,
    summary="Off-chain gnark verify + deployer confirm_verification on-chain",
)
async def verify_backend(req: VerifyBackendRequest):
    """
    Backend-only endpoint (deployer key required). Workflow:
      1. Runs gnark verify locally on the submitted proof JSON.
      2. If valid, calls ZKVerifierContract.confirm_verification() signed by the deployer.

    This is the trusted-backend leg of the staged verification pattern.
    """
    gnark_valid = await _prover.verify_proof(
        circuit=req.circuit,
        proof_json=req.proof_json,
    )

    if not gnark_valid:
        return VerifyBackendResponse(
            gnark_valid=False,
            message="Proof failed gnark verification.",
        )

    try:
        tx_id = _algorand.confirm_verification(
            user=req.user,
            proof_hash_hex=req.proof_hash,
        )
        return VerifyBackendResponse(
            gnark_valid=True,
            tx_id=tx_id,
            message="Proof confirmed on-chain.",
        )
    except Exception as exc:
        logger.error("confirm_verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Proof valid but on-chain confirmation failed: {exc}",
        ) from exc


# ──────────────────────── Status check ────────────────────────────────────


class ProofStatusResponse(BaseModel):
    is_valid: bool
    user: str
    proof_hash: str


@router.get(
    "/status",
    response_model=ProofStatusResponse,
    summary="Check whether a proof is confirmed on-chain",
)
async def proof_status(user: str, proof_hash: str):
    """
    Calls ZKVerifierContract.is_proof_valid() via simulate.
    Returns True only if the deployer has already called confirm_verification.
    """
    is_valid = _algorand.is_proof_valid(user=user, proof_hash_hex=proof_hash)
    return ProofStatusResponse(is_valid=is_valid, user=user, proof_hash=proof_hash)
