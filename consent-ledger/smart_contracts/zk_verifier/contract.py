from typing import Literal

from algopy import (
    ARC4Contract,
    BoxMap,
    Bytes,
    Global,
    Txn,
    UInt64,
    arc4,
    op,
)
from algopy.arc4 import abimethod


class ProofRecord(arc4.Struct):
    proof_hash: arc4.StaticArray[arc4.UInt8, Literal[32]]
    circuit_type: arc4.UInt8     # 0=age_range, 1=consent_commitment, 2=nullifier
    is_verified: arc4.Bool
    verified_round: arc4.UInt64
    consent_app_id: arc4.UInt64  # links back to ConsentLedger app


class ZKVerifierContract(ARC4Contract):
    """
    Staged Groth16 ZK proof verifier for ConsentLedger.

    AVM cannot perform EC pairings natively within the ~70k opcode budget.
    Two-phase strategy:
      1. User submits proof_hash on-chain (cheap: ~1000 ops)
      2. Trusted backend (contract creator) verifies off-chain via gnark, then
         calls confirm_verification() to mark the proof valid on-chain.
      3. ConsentLedger reads is_proof_valid() before granting consent.

    Box key = sha256(user_address || proof_hash) to fit within 64-byte AVM limit.
    """

    def __init__(self) -> None:
        # consent_ledger_app links proofs to a specific ConsentLedger deployment.
        # Updated post-deploy via set_consent_ledger_app() by the creator.
        self.consent_ledger_app = UInt64(0)
        # proofs keyed by sha256(submitter(32) || proof_hash(32)) = 32 bytes
        self.proofs = BoxMap(Bytes, ProofRecord, key_prefix=b"")

    @abimethod()
    def set_consent_ledger_app(self, app_id: arc4.UInt64) -> None:
        """Set the linked ConsentLedger app ID. Only the contract creator can call this."""
        assert Txn.sender == Global.creator_address, "Only creator can configure"
        self.consent_ledger_app = app_id.native

    @abimethod()
    def submit_proof(
        self,
        proof_hash: arc4.StaticArray[arc4.UInt8, Literal[32]],
        circuit_type: arc4.UInt8,
        consent_app_id: arc4.UInt64,
    ) -> None:
        """
        User submits the SHA-256 hash of their ZK proof.
        The actual proof is verified off-chain by the trusted backend (creator).
        Box key = sha256(sender || proof_hash) — fits within AVM 64-byte limit.
        """
        key = op.sha256(Txn.sender.bytes + proof_hash.bytes)
        assert key not in self.proofs, "Proof already submitted"
        record = ProofRecord(
            proof_hash=proof_hash.copy(),
            circuit_type=circuit_type,
            is_verified=arc4.Bool(False),
            verified_round=arc4.UInt64(0),
            consent_app_id=consent_app_id,
        )
        self.proofs[key] = record.copy()

    @abimethod()
    def confirm_verification(
        self,
        user: arc4.Address,
        proof_hash: arc4.StaticArray[arc4.UInt8, Literal[32]],
    ) -> None:
        """
        Marks a proof as verified after off-chain gnark verification.
        Only the contract creator (trusted backend deployer) can call this.
        """
        assert Txn.sender == Global.creator_address, "Only trusted backend can confirm"
        key = op.sha256(user.bytes + proof_hash.bytes)
        assert key in self.proofs, "Unknown proof — call submit_proof first"
        record = self.proofs[key].copy()
        assert not record.is_verified.native, "Proof already confirmed"
        self.proofs[key] = ProofRecord(
            proof_hash=record.proof_hash.copy(),
            circuit_type=record.circuit_type,
            is_verified=arc4.Bool(True),
            verified_round=arc4.UInt64(Global.round),
            consent_app_id=record.consent_app_id,
        ).copy()

    @abimethod(readonly=True)
    def is_proof_valid(
        self,
        user: arc4.Address,
        proof_hash: arc4.StaticArray[arc4.UInt8, Literal[32]],
    ) -> arc4.Bool:
        """Returns True if the proof has been confirmed by the trusted backend."""
        key = op.sha256(user.bytes + proof_hash.bytes)
        if key not in self.proofs:
            return arc4.Bool(False)
        return arc4.Bool(self.proofs[key].is_verified.native)
