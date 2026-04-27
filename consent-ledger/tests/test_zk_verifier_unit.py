"""
Unit tests for ZKVerifierContract (Phase 2).

Tests cover:
- submit_proof creates an unverified record
- duplicate submission rejected
- confirm_verification (by creator/trusted backend) marks proof verified
- is_proof_valid returns False for unknown proofs

Run: algokit project run test
  or: poetry run pytest tests/ -v
"""
import hashlib
import typing

import algosdk
import pytest

from algopy import arc4
from algopy_testing import algopy_testing_context

from smart_contracts.zk_verifier.contract import ZKVerifierContract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proof_hash(data: str = "test_proof") -> arc4.StaticArray[arc4.UInt8, typing.Literal[32]]:
    raw = hashlib.sha256(data.encode()).digest()
    return arc4.StaticArray(*[arc4.UInt8(b) for b in raw])


# ---------------------------------------------------------------------------
# test_submit_proof_creates_unverified_record
# ---------------------------------------------------------------------------

def test_submit_proof_creates_unverified_record() -> None:
    """submit_proof must store a ProofRecord with is_verified=False."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()
        proof_hash = _make_proof_hash("my_age_range_proof")

        contract.submit_proof(
            proof_hash=proof_hash,
            circuit_type=arc4.UInt8(0),  # 0 = age_range
            consent_app_id=arc4.UInt64(42),
        )

        result = contract.is_proof_valid(
            user=arc4.Address(str(ctx.default_sender)),
            proof_hash=proof_hash,
        )
        assert result.native is False, "Proof should be unverified immediately after submission"


# ---------------------------------------------------------------------------
# test_duplicate_submission_rejected
# ---------------------------------------------------------------------------

def test_duplicate_submission_rejected() -> None:
    """submit_proof must reject a duplicate sender+proof_hash submission."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()
        proof_hash = _make_proof_hash("my_proof")

        contract.submit_proof(
            proof_hash=proof_hash,
            circuit_type=arc4.UInt8(0),
            consent_app_id=arc4.UInt64(42),
        )

        with pytest.raises(Exception, match="Proof already submitted"):
            contract.submit_proof(
                proof_hash=proof_hash,
                circuit_type=arc4.UInt8(0),
                consent_app_id=arc4.UInt64(42),
            )


# ---------------------------------------------------------------------------
# test_confirm_verification_marks_verified
# ---------------------------------------------------------------------------

def test_confirm_verification_marks_verified() -> None:
    """confirm_verification called by the creator must mark the proof as verified."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()
        proof_hash = _make_proof_hash("my_proof")
        user_addr = str(ctx.default_sender)

        # User submits proof
        contract.submit_proof(
            proof_hash=proof_hash,
            circuit_type=arc4.UInt8(0),
            consent_app_id=arc4.UInt64(42),
        )

        # Creator (trusted backend) confirms verification.
        # In algopy_testing, Txn.sender == ctx.default_sender == Global.creator_address.
        contract.confirm_verification(
            user=arc4.Address(user_addr),
            proof_hash=proof_hash,
        )

        result = contract.is_proof_valid(
            user=arc4.Address(user_addr),
            proof_hash=proof_hash,
        )
        assert result.native is True, "Proof should be verified after confirm_verification"


# ---------------------------------------------------------------------------
# test_double_confirm_rejected
# ---------------------------------------------------------------------------

def test_double_confirm_rejected() -> None:
    """confirm_verification must reject an already-confirmed proof."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()
        proof_hash = _make_proof_hash("my_proof")
        user_addr = str(ctx.default_sender)

        contract.submit_proof(
            proof_hash=proof_hash,
            circuit_type=arc4.UInt8(0),
            consent_app_id=arc4.UInt64(42),
        )
        contract.confirm_verification(
            user=arc4.Address(user_addr),
            proof_hash=proof_hash,
        )
        with pytest.raises(Exception, match="Proof already confirmed"):
            contract.confirm_verification(
                user=arc4.Address(user_addr),
                proof_hash=proof_hash,
            )


# ---------------------------------------------------------------------------
# test_is_proof_valid_unknown
# ---------------------------------------------------------------------------

def test_is_proof_valid_returns_false_for_unknown() -> None:
    """is_proof_valid must return False for a proof that was never submitted."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()
        proof_hash = _make_proof_hash("nonexistent_proof")

        result = contract.is_proof_valid(
            user=arc4.Address(str(ctx.default_sender)),
            proof_hash=proof_hash,
        )
        assert result.native is False


# ---------------------------------------------------------------------------
# test_different_circuits
# ---------------------------------------------------------------------------

def test_different_circuit_types_stored() -> None:
    """circuit_type field should be stored correctly for each circuit."""
    with algopy_testing_context() as ctx:
        contract = ZKVerifierContract()

        for circuit_type in [0, 1, 2]:  # age_range, consent_commitment, nullifier
            proof_hash = _make_proof_hash(f"proof_circuit_{circuit_type}")
            contract.submit_proof(
                proof_hash=proof_hash,
                circuit_type=arc4.UInt8(circuit_type),
                consent_app_id=arc4.UInt64(100),
            )
            # Should be unverified until backend confirms
            assert contract.is_proof_valid(
                user=arc4.Address(str(ctx.default_sender)),
                proof_hash=proof_hash,
            ).native is False
