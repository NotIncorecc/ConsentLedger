"""
Unit tests for the upgraded ConsentLedger smart contract (Phase 2).

Tests cover ZK commitment/nullifier flow, anti-replay protection,
DPDP section storage, revocation, and consent validity checks.

Run: algokit project run test
  or: poetry run pytest tests/ -v
"""
import hashlib
import typing

import algosdk
import pytest

from algopy import arc4
from algopy_testing import algopy_testing_context

from smart_contracts.consent_ledger.contract import ConsentLedger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_address(contract: ConsentLedger) -> str:
    """Derive the Algorand application address from the contract's app_id."""
    return algosdk.logic.get_application_address(contract.__app_id__)


def _make_commitment(
    data_type: str = "medical_records",
    purpose: str = "annual health screening",
    salt: str = "test_salt_0001",
) -> arc4.StaticArray[arc4.UInt8, typing.Literal[32]]:
    """Simulate a Poseidon commitment using SHA-256 (test-only approximation)."""
    raw = hashlib.sha256(f"{data_type}:{purpose}:{salt}".encode()).digest()
    return arc4.StaticArray(*[arc4.UInt8(b) for b in raw])


def _make_nullifier(
    identity_secret: str = "test_identity_secret",
    consent_id: str = "consent_001",
) -> arc4.StaticArray[arc4.UInt8, typing.Literal[32]]:
    """Simulate SHA256(identity_secret || consent_id) for the nullifier."""
    raw = hashlib.sha256(f"{identity_secret}:{consent_id}".encode()).digest()
    return arc4.StaticArray(*[arc4.UInt8(b) for b in raw])


def _grant(
    contract: ConsentLedger,
    ctx,
    *,
    requester: str | None = None,
    identity_secret: str = "test_identity_secret",
    consent_id: str = "consent_001",
    dpdp_section: int = 6,
) -> int:
    """Call grant_consent and return the plain-int asset ID."""
    req = arc4.Address(requester or str(ctx.default_sender))
    result = contract.grant_consent(
        requester=req,
        commitment=_make_commitment(),
        nullifier=_make_nullifier(identity_secret, consent_id),
        expiry=arc4.UInt64(0),
        dpdp_section=arc4.UInt8(dpdp_section),
    )
    return int(result.native)


# ---------------------------------------------------------------------------
# test_grant_consent_creates_asa
# ---------------------------------------------------------------------------

def test_grant_consent_creates_asa() -> None:
    """grant_consent must return a valid asset ID for a ZK-committed consent."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        asset_id = _grant(contract, ctx)

        assert asset_id > 0, "Expected a non-zero asset ID"
        assert ctx.ledger.asset_exists(asset_id), f"Asset {asset_id} should exist in ledger"

        last_itxn = ctx.txn.last_group.last_itxn.asset_config
        assert int(last_itxn.created_asset.id) == asset_id


# ---------------------------------------------------------------------------
# test_nullifier_anti_replay
# ---------------------------------------------------------------------------

def test_nullifier_anti_replay() -> None:
    """grant_consent must reject a second call with the same nullifier."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        _grant(contract, ctx, consent_id="consent_001")

        # Same nullifier must be rejected
        with pytest.raises(Exception, match="Nullifier already used"):
            _grant(contract, ctx, consent_id="consent_001")


# ---------------------------------------------------------------------------
# test_different_nullifiers_allowed
# ---------------------------------------------------------------------------

def test_different_nullifiers_allowed() -> None:
    """Two different consent_ids produce different nullifiers — both grants succeed."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        id1 = _grant(contract, ctx, consent_id="consent_001")
        second_requester = algosdk.account.generate_account()[1]
        id2 = _grant(contract, ctx, requester=second_requester, consent_id="consent_002")

        assert id1 > 0
        assert id2 > 0
        assert id1 != id2


# ---------------------------------------------------------------------------
# test_dpdp_section_stored
# ---------------------------------------------------------------------------

def test_dpdp_section_stored() -> None:
    """The dpdp_section value must be persisted and readable from the consent record."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        requester_addr = str(ctx.default_sender)
        _grant(contract, ctx, requester=requester_addr, dpdp_section=9)

        record = contract.get_consent_record(
            owner=arc4.Address(str(ctx.default_sender)),
            requester=arc4.Address(requester_addr),
        )
        assert int(record.dpdp_section.native) == 9


# ---------------------------------------------------------------------------
# test_get_consent_record_returns_commitment
# ---------------------------------------------------------------------------

def test_get_consent_record_returns_commitment_not_plaintext() -> None:
    """get_consent_record must return the commitment bytes, not plaintext strings."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        requester_addr = str(ctx.default_sender)
        commitment = _make_commitment("medical_records", "screening", "salt1")
        contract.grant_consent(
            requester=arc4.Address(requester_addr),
            commitment=commitment,
            nullifier=_make_nullifier(),
            expiry=arc4.UInt64(0),
            dpdp_section=arc4.UInt8(6),
        )
        record = contract.get_consent_record(
            owner=arc4.Address(str(ctx.default_sender)),
            requester=arc4.Address(requester_addr),
        )
        assert record.commitment.bytes == commitment.bytes


# ---------------------------------------------------------------------------
# test_revoke_freezes_asset
# ---------------------------------------------------------------------------

def test_revoke_freezes_asset() -> None:
    """revoke_consent must submit an AssetFreeze inner transaction with frozen=True."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        requester_addr = str(ctx.default_sender)
        asset_id = _grant(contract, ctx, requester=requester_addr)
        app_addr = _app_address(contract)

        ctx.ledger.update_asset_holdings(asset_id, app_addr, balance=1, frozen=False)
        contract.revoke_consent(arc4.Address(requester_addr))

        freeze_itxn = ctx.txn.last_group.last_itxn.asset_freeze
        assert freeze_itxn.frozen is True, "Expected frozen=True"
        assert int(freeze_itxn.freeze_asset.id) == asset_id


# ---------------------------------------------------------------------------
# test_is_valid_returns_false_when_frozen
# ---------------------------------------------------------------------------

def test_is_valid_returns_false_when_frozen() -> None:
    """is_consent_valid must return False after the consent ASA has been frozen."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        owner_addr = str(ctx.default_sender)
        requester_addr = str(ctx.default_sender)
        asset_id = _grant(contract, ctx, requester=requester_addr)
        app_addr = _app_address(contract)

        before = contract.is_consent_valid(
            owner=arc4.Address(owner_addr),
            requester=arc4.Address(requester_addr),
        )
        assert before.native is True, "Consent should be valid before revocation"

        ctx.ledger.update_asset_holdings(asset_id, app_addr, balance=1, frozen=True)

        after = contract.is_consent_valid(
            owner=arc4.Address(owner_addr),
            requester=arc4.Address(requester_addr),
        )
        assert after.native is False, "Consent should be invalid after ASA frozen"


# ---------------------------------------------------------------------------
# test_is_valid_missing_record
# ---------------------------------------------------------------------------

def test_is_valid_returns_false_for_missing_record() -> None:
    """is_consent_valid must return False when no consent record exists."""
    with algopy_testing_context() as ctx:
        contract = ConsentLedger()
        random_addr = algosdk.account.generate_account()[1]
        result = contract.is_consent_valid(
            owner=arc4.Address(str(ctx.default_sender)),
            requester=arc4.Address(random_addr),
        )
        assert result.native is False
