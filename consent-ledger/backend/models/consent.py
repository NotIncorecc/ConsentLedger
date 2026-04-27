"""
models/consent.py — Pydantic v2 models for consent operations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConsentGrantRequest(BaseModel):
    """Request body for POST /consent/grant."""

    requester: str = Field(
        ...,
        description="Algorand address of the organisation requesting consent.",
        examples=["AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"],
    )
    commitment: str = Field(
        ...,
        description="Hex-encoded 32-byte Poseidon commitment (Poseidon(data_type_hash, purpose_hash, salt)).",
        min_length=64,
        max_length=64,
    )
    nullifier: str = Field(
        ...,
        description="Hex-encoded 32-byte nullifier (SHA256(identity_secret || consent_id)).",
        min_length=64,
        max_length=64,
    )
    expiry: int = Field(
        default=0,
        description="Unix timestamp after which consent expires. 0 = no expiry.",
        ge=0,
    )
    dpdp_section: int = Field(
        default=6,
        description="DPDP Act section (6=§6 Standard, 9=§9 Children, 11=§11 Grievance, 16=§16 DPB Audit).",
        ge=6,
        le=16,
    )
    sender: str = Field(
        ...,
        description="Algorand address of the user signing the transaction (tx.Sender).",
    )


class ConsentGrantResponse(BaseModel):
    """Response for a successful consent grant transaction preparation."""

    unsigned_txn_b64: str = Field(
        ...,
        description=(
            "Base64-encoded msgpack unsigned ApplicationCallTxn. "
            "Sign with the user's wallet and submit via algod."
        ),
    )
    asset_id_hint: str = Field(
        default="",
        description="Available after the signed txn is confirmed on-chain.",
    )


class ConsentRevokeRequest(BaseModel):
    """Request body for POST /consent/revoke."""

    requester: str = Field(
        ...,
        description="Algorand address of the organisation whose consent is being revoked.",
    )
    sender: str = Field(
        ...,
        description="Algorand address of the consent owner (must match original owner on-chain).",
    )


class ConsentRevokeResponse(BaseModel):
    unsigned_txn_b64: str


class ConsentRecord(BaseModel):
    """On-chain consent record returned by get_consent_record."""

    owner: str
    requester: str
    commitment: str = Field(..., description="Hex-encoded 32-byte Poseidon commitment.")
    nullifier: str = Field(..., description="Hex-encoded 32-byte nullifier.")
    expiry: int
    asset_id: int
    dpdp_section: int


class ConsentValidityResponse(BaseModel):
    is_valid: bool
    owner: str
    requester: str
