"""
routers/payments.py — x402 micropayment gate helpers and org management.

POST /payments/create-payment-txn  → unsigned ALGO payment txn for requester
GET  /org/check-authorization      → is_org_authorized() read-only query
POST /org/register                 → register_org() admin-only
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from config import settings
from services.algorand import AlgorandService

logger = logging.getLogger(__name__)

# Two routers: one for payment helpers, one for org registry
payments_router = APIRouter(prefix="/payments", tags=["payments"])
org_router = APIRouter(prefix="/org", tags=["org"])

# ──────────────────────── Singleton ───────────────────────────────────────

_algorand = AlgorandService(
    algod_server=settings.algod_server,
    algod_token=settings.algod_token,
    deployer_mnemonic_phrase=settings.deployer_mnemonic,
    consent_ledger_app_id=settings.consent_ledger_app_id,
    zk_verifier_app_id=settings.zk_verifier_app_id,
    org_registry_app_id=settings.org_registry_app_id,
)

# ══════════════════════════ Payments ══════════════════════════════════════


class CreatePaymentTxnRequest(BaseModel):
    payer: str = Field(..., description="Algorand address of the verifier paying the fee.")
    note: str = Field(
        default="ConsentLedger|consent_fee",
        description="Optional human-readable note on the payment.",
    )


class CreatePaymentTxnResponse(BaseModel):
    receiver: str
    amount_microalgo: int
    unsigned_txn_b64: str
    instructions: str


@payments_router.post(
    "/create-payment-txn",
    response_model=CreatePaymentTxnResponse,
    summary="Create unsigned ALGO payment txn for consent verification fee",
)
async def create_payment_txn(req: CreatePaymentTxnRequest):
    """
    Returns an unsigned PaymentTxn (base64 msgpack) that the requester's
    wallet should sign. Include the signed txn in the `X-Payment` header
    when calling `GET /consent/verify`.

    Fee: `CONSENT_FEE_MICROALGO` (default 100,000 microAlgo = 0.1 ALGO)
    Receiver: deployer address (ConsentLedger operator)
    """
    if not _algorand.deployer_address:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployer address not configured — free mode active.",
        )

    note_bytes = req.note.encode("utf-8")[:32]  # AVM note max 1KB but keep compact
    unsigned_b64 = _algorand.build_payment_txn(
        payer=req.payer,
        receiver=_algorand.deployer_address,
        amount_microalgo=settings.consent_fee_microalgo,
        note=note_bytes,
    )
    return CreatePaymentTxnResponse(
        receiver=_algorand.deployer_address,
        amount_microalgo=settings.consent_fee_microalgo,
        unsigned_txn_b64=unsigned_b64,
        instructions=(
            "Sign this transaction with your wallet and include the base64-encoded "
            "signed txn in the X-Payment header of GET /consent/verify."
        ),
    )


# ══════════════════════════ Org Registry ══════════════════════════════════


class RegisterOrgRequest(BaseModel):
    org_address: str = Field(..., description="Algorand address of the organisation.")
    name: str = Field(..., max_length=128)
    dpdp_license: str = Field(..., description="DPDP Data Fiduciary registration number.")
    allowed_types: int = Field(
        ...,
        description="Bitmask of allowed data fields (bit0=name, bit1=dob, bit2=address, …).",
        ge=0,
        le=65535,
    )
    x402_wallet: str = Field(..., description="Wallet used for x402 consent fee payments.")


class RegisterOrgResponse(BaseModel):
    tx_id: str
    org_address: str
    message: str


@org_router.post(
    "/register",
    response_model=RegisterOrgResponse,
    summary="Register a new Data Fiduciary (admin-only)",
)
async def register_org(req: RegisterOrgRequest):
    """
    Calls OrgRegistryContract.register_org() signed by the deployer.
    Only the contract creator can register organisations.
    """
    try:
        tx_id = _algorand.register_org(
            org_address=req.org_address,
            name=req.name,
            dpdp_license=req.dpdp_license,
            allowed_types=req.allowed_types,
            x402_wallet=req.x402_wallet,
        )
    except Exception as exc:
        logger.error("register_org failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return RegisterOrgResponse(
        tx_id=tx_id,
        org_address=req.org_address,
        message=f"Organisation {req.name} registered successfully.",
    )


class OrgAuthResponse(BaseModel):
    org: str
    requested_field_mask: int
    is_authorized: bool


@org_router.get(
    "/check-authorization",
    response_model=OrgAuthResponse,
    summary="Check whether an org is authorised for given data fields",
)
async def check_org_authorization(
    org: str = Query(..., description="Algorand address of the organisation."),
    field_mask: int = Query(
        ...,
        description="Bitmask of requested data fields.",
        ge=1,
        le=65535,
    ),
):
    """
    Calls OrgRegistryContract.is_org_authorized() via simulate.
    Returns True only if the org is active and all requested bits are
    included in the org's `allowed_types` bitmask.
    """
    try:
        is_auth = _algorand.is_org_authorized(org=org, requested_field_mask=field_mask)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid address or contract error: {exc}") from exc
    return OrgAuthResponse(
        org=org,
        requested_field_mask=field_mask,
        is_authorized=is_auth,
    )
