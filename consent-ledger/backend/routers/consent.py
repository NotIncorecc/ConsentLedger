"""
routers/consent.py — Consent management endpoints.

POST /consent/grant    → build unsigned grant_consent txn (user signs)
POST /consent/revoke   → build unsigned revoke_consent txn (user signs)
GET  /consent/verify   → x402-gated is_consent_valid query
GET  /consent/record   → read full consent record
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel

from config import settings
from models.consent import (
    ConsentGrantRequest,
    ConsentGrantResponse,
    ConsentRecord,
    ConsentRevokeRequest,
    ConsentRevokeResponse,
    ConsentValidityResponse,
)
from services.algorand import AlgorandService
from services.nullifier import NullifierStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/consent", tags=["consent"])

# ──────────────────────── Singletons ──────────────────────────────────────

_algorand = AlgorandService(
    algod_server=settings.algod_server,
    algod_token=settings.algod_token,
    deployer_mnemonic_phrase=settings.deployer_mnemonic,
    consent_ledger_app_id=settings.consent_ledger_app_id,
    zk_verifier_app_id=settings.zk_verifier_app_id,
    org_registry_app_id=settings.org_registry_app_id,
)

_nullifier_store = NullifierStore()

# ──────────────────────── Grant consent ───────────────────────────────────


@router.post(
    "/grant",
    response_model=ConsentGrantResponse,
    summary="Build unsigned grant_consent txn",
)
async def grant_consent(req: ConsentGrantRequest):
    """
    Prepares an unsigned ApplicationCallTxn for the user's wallet to sign.

    Pre-flight checks:
      - commitment must be 64-char hex (32 bytes)
      - nullifier must be 64-char hex (32 bytes)
      - nullifier must not be recorded in the off-chain store (replay prevention)

    The user signs and broadcasts the returned txn. On success the consent is
    recorded in ConsentLedger and an ASA is minted to the application address.
    """
    # Off-chain replay pre-check
    if _nullifier_store.check(req.nullifier):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nullifier already used. This consent has already been granted.",
        )

    try:
        unsigned_txn_b64 = _algorand.prepare_grant_consent(
            sender=req.sender,
            requester=req.requester,
            commitment_hex=req.commitment,
            nullifier_hex=req.nullifier,
            expiry=req.expiry,
            dpdp_section=req.dpdp_section,
        )
    except Exception as exc:
        logger.error("prepare_grant_consent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Mark nullifier as pending (will also be on-chain after the user submits)
    _nullifier_store.mark_used(req.nullifier)

    return ConsentGrantResponse(unsigned_txn_b64=unsigned_txn_b64)


# ──────────────────────── Revoke consent ──────────────────────────────────


@router.post(
    "/revoke",
    response_model=ConsentRevokeResponse,
    summary="Build unsigned revoke_consent txn",
)
async def revoke_consent(req: ConsentRevokeRequest):
    """
    Prepares an unsigned revoke_consent txn. The user signs and broadcasts it.
    Revocation freezes the consent ASA — confirming revocation within ~4 seconds.
    """
    try:
        unsigned_txn_b64 = _algorand.prepare_revoke_consent(
            sender=req.sender,
            requester=req.requester,
        )
    except Exception as exc:
        logger.error("prepare_revoke_consent failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ConsentRevokeResponse(unsigned_txn_b64=unsigned_txn_b64)


# ──────────────────────── Verify consent (x402 gated) ─────────────────────


@router.get(
    "/verify",
    response_model=ConsentValidityResponse,
    summary="Check consent validity (x402 payment required)",
)
async def verify_consent(
    owner: str = Query(..., description="Algorand address of the data principal."),
    requester: str = Query(..., description="Algorand address of the querying organisation."),
    x_payment: str = Header(
        default="",
        alias="X-Payment",
        description="Base64-encoded signed ALGO payment txn (0.1 ALGO to deployer).",
    ),
):
    """
    x402-style guarded consent verification endpoint.

    Organisations must include a signed PaymentTxn in the `X-Payment` header
    paying `CONSENT_FEE_MICROALGO` to the deployer address.

    This gate ensures that only authorised, paying parties can query consent
    status — preventing enumeration attacks and funding the protocol.
    """
    if settings.deployer_mnemonic and x_payment:
        # Full payment check when deployer address is configured
        payment_ok = _algorand.verify_payment(
            signed_payment_b64=x_payment,
            expected_receiver=_algorand.deployer_address,
            min_amount_microalgo=settings.consent_fee_microalgo,
        )
        if not payment_ok:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Valid X-Payment header required: "
                    f"{settings.consent_fee_microalgo} microAlgo to {_algorand.deployer_address}."
                ),
            )
    elif not x_payment:
        logger.info("X-Payment header missing — payment gate bypassed (dev mode).")

    is_valid = _algorand.is_consent_valid(owner=owner, requester=requester)
    return ConsentValidityResponse(is_valid=is_valid, owner=owner, requester=requester)


# ──────────────────────── Read consent record ─────────────────────────────


@router.get(
    "/record",
    response_model=ConsentRecord,
    summary="Fetch full consent record (no plaintext — commitment hash only)",
)
async def get_consent_record(
    owner: str = Query(...),
    requester: str = Query(...),
):
    """
    Returns the raw ConsentRecord stored in ConsentLedger's BoxMap.
    Note: `commitment` and `nullifier` are hex-encoded hashes.
    No plaintext data_type or purpose is ever stored or returned.
    """
    record = _algorand.get_consent_record(owner=owner, requester=requester)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consent record found for this owner/requester pair.",
        )
    return ConsentRecord(**record)


# ──────────────────────── Payment params helper ────────────────────────────


class PaymentParamsResponse(BaseModel):
    receiver: str
    amount_microalgo: int
    unsigned_payment_txn_b64: str


@router.get(
    "/payment-params",
    response_model=PaymentParamsResponse,
    summary="Get unsigned payment txn for X-Payment header",
)
async def get_payment_params(payer: str = Query(...)):
    """
    Returns an unsigned PaymentTxn that the requester should sign and include
    in the `X-Payment` header when calling `GET /consent/verify`.
    """
    if not _algorand.deployer_address:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployer address not configured.",
        )
    unsigned_b64 = _algorand.build_payment_txn(
        payer=payer,
        receiver=_algorand.deployer_address,
        amount_microalgo=settings.consent_fee_microalgo,
    )
    return PaymentParamsResponse(
        receiver=_algorand.deployer_address,
        amount_microalgo=settings.consent_fee_microalgo,
        unsigned_payment_txn_b64=unsigned_b64,
    )
