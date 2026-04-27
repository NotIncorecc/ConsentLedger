"""
services/algorand.py — Algorand blockchain interactions for ConsentLedger.

Responsibilities:
  - Build unsigned ApplicationCallTxns for user-signed operations
    (grant_consent, revoke_consent, submit_proof).
  - Sign and submit backend-signed operations (confirm_verification).
  - Execute read-only queries (is_consent_valid, is_org_authorized, etc.).

All ARC-4 ABI encoding is done with algosdk.abi.  Box references are
included in every transaction that touches BoxMap state so the AVM can
allocate and access storage within the opcode budget.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

from algosdk import encoding, mnemonic
from algosdk.account import address_from_private_key
from algosdk.abi import ABIType, Method
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.encoding import msgpack_encode
from algosdk.transaction import ApplicationCallTxn, OnComplete
from algosdk.v2client import algod as _algod

logger = logging.getLogger(__name__)

# ──────────────────────── ABI type singletons ─────────────────────────────

_T_ADDRESS = ABIType.from_string("address")
_T_BYTES32 = ABIType.from_string("uint8[32]")
_T_UINT64 = ABIType.from_string("uint64")
_T_UINT16 = ABIType.from_string("uint16")
_T_UINT8 = ABIType.from_string("uint8")
_T_BOOL = ABIType.from_string("bool")

# ──────────────────────── Method selectors (4-byte ABI prefix) ────────────

_METHODS = {
    "grant_consent": Method.from_signature(
        "grant_consent(address,uint8[32],uint8[32],uint64,uint8)uint64"
    ),
    "revoke_consent": Method.from_signature("revoke_consent(address)void"),
    "is_consent_valid": Method.from_signature("is_consent_valid(address,address)bool"),
    "get_consent_record": Method.from_signature(
        "get_consent_record(address,address)(address,address,uint8[32],uint8[32],uint64,uint64,uint8)"
    ),
    "submit_proof": Method.from_signature(
        "submit_proof(uint8[32],uint8,uint64)void"
    ),
    "confirm_verification": Method.from_signature(
        "confirm_verification(address,uint8[32])void"
    ),
    "is_proof_valid": Method.from_signature("is_proof_valid(address,uint8[32])bool"),
    "register_org": Method.from_signature(
        "register_org(address,string,string,uint16,address)void"
    ),
    "is_org_authorized": Method.from_signature(
        "is_org_authorized(address,uint16)bool"
    ),
}


def _selector(name: str) -> bytes:
    return _METHODS[name].get_selector()


def _hex_to_bytes32_list(hex_str: str) -> list[int]:
    """Convert a 64-char hex string to a list of 32 ints for ABI uint8[32]."""
    raw = bytes.fromhex(hex_str)
    if len(raw) != 32:
        raise ValueError(f"Expected 32 bytes, got {len(raw)}: {hex_str}")
    return list(raw)


def _encode_unsigned_txn(txn: ApplicationCallTxn) -> str:
    """Return the unsigned transaction as a base64 msgpack string."""
    return msgpack_encode(txn)

class AlgorandService:
    """Façade for all on-chain interactions."""

    def __init__(
        self,
        algod_server: str,
        algod_token: str,
        deployer_mnemonic_phrase: str,
        consent_ledger_app_id: int,
        zk_verifier_app_id: int,
        org_registry_app_id: int,
    ) -> None:
        self.algod = _algod.AlgodClient(algod_token, algod_server)
        self.consent_ledger_app_id = consent_ledger_app_id
        self.zk_verifier_app_id = zk_verifier_app_id
        self.org_registry_app_id = org_registry_app_id

        if deployer_mnemonic_phrase:
            pk = mnemonic.to_private_key(deployer_mnemonic_phrase)
            self.deployer_address: str = address_from_private_key(pk)
            self._deployer_signer = AccountTransactionSigner(pk)
        else:
            self.deployer_address = ""
            self._deployer_signer = None  # type: ignore[assignment]
            logger.warning("No deployer mnemonic configured — backend-signed calls will fail.")

    # ──────────────────────── Suggested params helper ─────────────────────

    def _sp(self, flat_fee: int = 1000):
        sp = self.algod.suggested_params()
        sp.flat_fee = True
        sp.fee = flat_fee
        return sp

    # ═══════════════════════ ConsentLedger ════════════════════════════════

    def prepare_grant_consent(
        self,
        sender: str,
        requester: str,
        commitment_hex: str,
        nullifier_hex: str,
        expiry: int,
        dpdp_section: int,
    ) -> str:
        """
        Build an unsigned grant_consent ApplicationCallTxn for the user's wallet.

        Inner txn (ASA creation) requires fee=2000.
        Box refs: nullifier box + consent record box.

        Returns base64 msgpack unsigned txn string.
        """
        sp = self._sp(flat_fee=2000)

        sender_bytes = encoding.decode_address(sender)
        requester_bytes = encoding.decode_address(requester)
        commitment_list = _hex_to_bytes32_list(commitment_hex)
        nullifier_bytes = bytes.fromhex(nullifier_hex)
        nullifier_list = list(nullifier_bytes)

        app_args = [
            _selector("grant_consent"),
            _T_ADDRESS.encode(requester),
            _T_BYTES32.encode(commitment_list),
            _T_BYTES32.encode(nullifier_list),
            _T_UINT64.encode(expiry),
            _T_UINT8.encode(dpdp_section),
        ]

        # Box keys — must match on-chain key derivation exactly
        null_box = b"null_" + nullifier_bytes          # nullifiers BoxMap
        consent_box = sender_bytes + requester_bytes   # consents BoxMap (no prefix)

        txn = ApplicationCallTxn(
            sender=sender,
            sp=sp,
            index=self.consent_ledger_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[
                (self.consent_ledger_app_id, null_box),
                (self.consent_ledger_app_id, consent_box),
            ],
        )
        return _encode_unsigned_txn(txn)

    def prepare_revoke_consent(self, sender: str, requester: str) -> str:
        """
        Build an unsigned revoke_consent ApplicationCallTxn.

        Inner txn (ASA freeze) requires fee=2000.
        Returns base64 msgpack unsigned txn string.
        """
        sp = self._sp(flat_fee=2000)

        sender_bytes = encoding.decode_address(sender)
        requester_bytes = encoding.decode_address(requester)
        consent_box = sender_bytes + requester_bytes

        app_args = [
            _selector("revoke_consent"),
            _T_ADDRESS.encode(requester),
        ]

        txn = ApplicationCallTxn(
            sender=sender,
            sp=sp,
            index=self.consent_ledger_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.consent_ledger_app_id, consent_box)],
        )
        return _encode_unsigned_txn(txn)

    def is_consent_valid(self, owner: str, requester: str) -> bool:
        """
        Simulate is_consent_valid(owner, requester) as a read-only dry run.

        Uses algod's simulate endpoint (no fee required).
        """
        sp = self._sp()
        owner_bytes = encoding.decode_address(owner)
        requester_bytes = encoding.decode_address(requester)
        consent_box = owner_bytes + requester_bytes

        app_args = [
            _selector("is_consent_valid"),
            _T_ADDRESS.encode(owner),
            _T_ADDRESS.encode(requester),
        ]

        txn = ApplicationCallTxn(
            sender=owner,
            sp=sp,
            index=self.consent_ledger_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.consent_ledger_app_id, consent_box)],
        )

        result = self._simulate(txn, owner)
        if not result:
            return False

        # ABI bool return: 4-byte prefix + 1-byte value (0x80 = True, 0x00 = False)
        log_data = self._extract_log(result)
        if log_data is None or len(log_data) < 5:
            return False
        return log_data[4] == 0x80

    def get_consent_record(self, owner: str, requester: str) -> dict[str, Any] | None:
        """Read the full consent record for owner/requester via simulate."""
        sp = self._sp()
        owner_bytes = encoding.decode_address(owner)
        requester_bytes = encoding.decode_address(requester)
        consent_box = owner_bytes + requester_bytes

        app_args = [
            _selector("get_consent_record"),
            _T_ADDRESS.encode(owner),
            _T_ADDRESS.encode(requester),
        ]
        txn = ApplicationCallTxn(
            sender=owner,
            sp=sp,
            index=self.consent_ledger_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.consent_ledger_app_id, consent_box)],
        )
        result = self._simulate(txn, owner)
        if not result:
            return None

        log_data = self._extract_log(result)
        if log_data is None or len(log_data) < 5:
            return None

        # Parse the returned ABI struct (skip 4-byte ABI log prefix)
        raw = log_data[4:]
        struct_type = ABIType.from_string(
            "(address,address,uint8[32],uint8[32],uint64,uint64,uint8)"
        )
        try:
            decoded = struct_type.decode(raw)
        except Exception as exc:
            logger.error("Failed to decode consent record: %s", exc)
            return None

        return {
            "owner": decoded[0],
            "requester": decoded[1],
            "commitment": bytes(decoded[2]).hex(),
            "nullifier": bytes(decoded[3]).hex(),
            "expiry": decoded[4],
            "asset_id": decoded[5],
            "dpdp_section": decoded[6],
        }

    # ═══════════════════════ ZKVerifierContract ═══════════════════════════

    def prepare_submit_proof(
        self,
        sender: str,
        proof_hash_hex: str,
        circuit_type: int,
        consent_app_id: int,
    ) -> str:
        """
        Build an unsigned submit_proof ApplicationCallTxn.

        Box key = sha256(sender_bytes + proof_hash) — matches on-chain derivation.
        Returns base64 msgpack unsigned txn string.
        """
        sp = self._sp()
        sender_bytes = encoding.decode_address(sender)
        proof_hash_bytes = bytes.fromhex(proof_hash_hex)

        # On-chain: key = op.sha256(Txn.sender.bytes + proof_hash.bytes)
        box_key = hashlib.sha256(sender_bytes + proof_hash_bytes).digest()

        app_args = [
            _selector("submit_proof"),
            _T_BYTES32.encode(list(proof_hash_bytes)),
            _T_UINT8.encode(circuit_type),
            _T_UINT64.encode(consent_app_id),
        ]

        txn = ApplicationCallTxn(
            sender=sender,
            sp=sp,
            index=self.zk_verifier_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.zk_verifier_app_id, box_key)],
        )
        return _encode_unsigned_txn(txn)

    def confirm_verification(self, user: str, proof_hash_hex: str) -> str:
        """
        Sign and submit confirm_verification() as the deployer (trusted backend).

        Returns the confirmed transaction ID.
        Raises RuntimeError if no deployer mnemonic is configured.
        """
        if self._deployer_signer is None:
            raise RuntimeError("Deployer mnemonic not configured.")

        sp = self._sp()
        user_bytes = encoding.decode_address(user)
        proof_hash_bytes = bytes.fromhex(proof_hash_hex)
        box_key = hashlib.sha256(user_bytes + proof_hash_bytes).digest()

        app_args = [
            _selector("confirm_verification"),
            _T_ADDRESS.encode(user),
            _T_BYTES32.encode(list(proof_hash_bytes)),
        ]

        txn = ApplicationCallTxn(
            sender=self.deployer_address,
            sp=sp,
            index=self.zk_verifier_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.zk_verifier_app_id, box_key)],
        )

        atc = AtomicTransactionComposer()
        atc.add_transaction(TransactionWithSigner(txn, self._deployer_signer))
        atc.execute(self.algod, 4)

        # Return the tx ID of the confirmed transaction
        tx_id = atc.tx_ids[0]
        logger.info("confirm_verification confirmed: tx_id=%s", tx_id)
        return tx_id

    def is_proof_valid(self, user: str, proof_hash_hex: str) -> bool:
        """Simulate is_proof_valid read-only call."""
        sp = self._sp()
        user_bytes = encoding.decode_address(user)
        proof_hash_bytes = bytes.fromhex(proof_hash_hex)
        box_key = hashlib.sha256(user_bytes + proof_hash_bytes).digest()

        app_args = [
            _selector("is_proof_valid"),
            _T_ADDRESS.encode(user),
            _T_BYTES32.encode(list(proof_hash_bytes)),
        ]
        txn = ApplicationCallTxn(
            sender=user,
            sp=sp,
            index=self.zk_verifier_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.zk_verifier_app_id, box_key)],
        )
        result = self._simulate(txn, user)
        if not result:
            return False
        log_data = self._extract_log(result)
        if log_data is None or len(log_data) < 5:
            return False
        return log_data[4] == 0x80

    # ═══════════════════════ OrgRegistryContract ══════════════════════════

    def is_org_authorized(self, org: str, requested_field_mask: int) -> bool:
        """Simulate is_org_authorized read-only call."""
        sp = self._sp()
        org_bytes = encoding.decode_address(org)
        org_box = b"org_" + org_bytes

        app_args = [
            _selector("is_org_authorized"),
            _T_ADDRESS.encode(org),
            _T_UINT16.encode(requested_field_mask),
        ]
        txn = ApplicationCallTxn(
            sender=org,
            sp=sp,
            index=self.org_registry_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.org_registry_app_id, org_box)],
        )
        result = self._simulate(txn, org)
        if not result:
            return False
        log_data = self._extract_log(result)
        if log_data is None or len(log_data) < 5:
            return False
        return log_data[4] == 0x80

    def register_org(
        self,
        org_address: str,
        name: str,
        dpdp_license: str,
        allowed_types: int,
        x402_wallet: str,
    ) -> str:
        """
        Sign and submit register_org() as the deployer (admin-only).

        Returns confirmed tx ID.
        """
        if self._deployer_signer is None:
            raise RuntimeError("Deployer mnemonic not configured.")

        sp = self._sp()
        org_bytes = encoding.decode_address(org_address)
        org_box = b"org_" + org_bytes

        # ABI string encoding: 2-byte length prefix + UTF-8 bytes
        def encode_string(s: str) -> bytes:
            b = s.encode("utf-8")
            return len(b).to_bytes(2, "big") + b

        app_args = [
            _selector("register_org"),
            _T_ADDRESS.encode(org_address),
            encode_string(name),
            encode_string(dpdp_license),
            _T_UINT16.encode(allowed_types),
            _T_ADDRESS.encode(x402_wallet),
        ]

        txn = ApplicationCallTxn(
            sender=self.deployer_address,
            sp=sp,
            index=self.org_registry_app_id,
            on_complete=OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[(self.org_registry_app_id, org_box)],
        )

        atc = AtomicTransactionComposer()
        atc.add_transaction(TransactionWithSigner(txn, self._deployer_signer))
        atc.execute(self.algod, 4)
        tx_id = atc.tx_ids[0]
        logger.info("register_org confirmed: tx_id=%s", tx_id)
        return tx_id

    # ═══════════════════════ x402 Payment helpers ════════════════════════

    def build_payment_txn(
        self,
        payer: str,
        receiver: str,
        amount_microalgo: int,
        note: bytes = b"ConsentLedger|consent_fee",
    ) -> str:
        """Build an unsigned PaymentTxn. Returns base64 msgpack."""
        from algosdk.transaction import PaymentTxn
        from algosdk.encoding import msgpack_encode as _mpe

        sp = self._sp()
        txn = PaymentTxn(
            sender=payer,
            sp=sp,
            receiver=receiver,
            amt=amount_microalgo,
            note=note,
        )
        return _mpe(txn)

    def verify_payment(
        self,
        signed_payment_b64: str,
        expected_receiver: str,
        min_amount_microalgo: int,
    ) -> bool:
        """
        Decode and validate a signed payment transaction without submitting it.

        Checks:
          - receiver == expected_receiver
          - amount >= min_amount_microalgo
          - note contains "ConsentLedger"
        Does NOT verify the cryptographic signature (trust the network for that).
        """
        from algosdk.transaction import SignedTransaction

        try:
            raw = base64.b64decode(signed_payment_b64)
            import msgpack  # type: ignore[import]

            decoded = msgpack.unpackb(raw, raw=False)
            txn_fields = decoded.get("txn", {})
            rcv = encoding.encode_address(txn_fields.get("rcv", b""))
            amt = txn_fields.get("amt", 0)
            note = txn_fields.get("note", b"")
        except Exception as exc:
            logger.warning("Payment verification failed to decode txn: %s", exc)
            return False

        if rcv != expected_receiver:
            logger.warning("Payment receiver mismatch: got %s expected %s", rcv, expected_receiver)
            return False
        if amt < min_amount_microalgo:
            logger.warning("Payment amount too low: %d < %d", amt, min_amount_microalgo)
            return False
        if b"ConsentLedger" not in note:
            logger.warning("Payment note missing ConsentLedger marker.")
            return False

        return True

    # ══════════════════════ Internals ════════════════════════════════════

    def _simulate(self, txn: ApplicationCallTxn, sender: str) -> dict | None:
        """
        Execute a read-only simulate call via the algod API.

        Uses a zero-balance dummy signer so no real funds are required.
        """
        from algosdk.atomic_transaction_composer import (
            EmptySigner,
            AtomicTransactionComposer,
            TransactionWithSigner,
        )
        from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig

        try:
            atc = AtomicTransactionComposer()
            atc.add_transaction(TransactionWithSigner(txn, EmptySigner()))
            sim_result = atc.simulate(self.algod)
            groups = sim_result.simulate_response.get("txn-groups", [])
            if not groups:
                return None
            return groups[0].get("txn-results", [{}])[0]
        except Exception as exc:
            logger.debug("Simulate call failed: %s", exc)
            return None

    @staticmethod
    def _extract_log(sim_txn_result: dict) -> bytes | None:
        """Extract the first ABI log entry from a simulate txn result."""
        try:
            logs = sim_txn_result.get("txn", {}).get("logs", [])
            if not logs:
                return None
            return base64.b64decode(logs[0])
        except Exception:
            return None
