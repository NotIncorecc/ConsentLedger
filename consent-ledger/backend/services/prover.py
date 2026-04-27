"""
services/prover.py — ZK proof generation via the gnark CLI binary.

The gnark prover binary (compiled from consent-ledger/circuits/) accepts
JSON witness data and outputs a ProofOutput JSON containing:
  - proof: base64-encoded Groth16 proof bytes
  - public_inputs: map of hex-encoded field elements
  - proof_hash: SHA-256(proof_bytes) as hex — submitted on-chain to ZKVerifier

SIMULATION MODE: When the binary is absent the service falls back to
SHA-256-based simulation so the full backend flow can be exercised
without a compiled Go binary. Simulation proofs are clearly flagged
with `is_simulation: True` and must not be submitted to a production
ZKVerifier contract.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ProverService:
    """Thin wrapper around the gnark CLI binary."""

    def __init__(self, prover_binary: str, keys_dir: str) -> None:
        self.binary = Path(prover_binary).resolve()
        self.keys_dir = Path(keys_dir).resolve()
        self._has_binary = self.binary.exists()

        if not self._has_binary:
            logger.warning(
                "ProverService: gnark binary not found at %s. "
                "Running in simulation mode — proofs are SHA-256 approximations.",
                self.binary,
            )

    # ──────────────────────── Age range ───────────────────────────────────

    async def prove_age_range(
        self,
        secret_age: int,
        salt: int,
        min_age: int = 18,
        max_age: int = 120,
    ) -> dict:
        """
        Prove: min_age ≤ secret_age ≤ max_age without revealing secret_age.

        commitment = Poseidon(secret_age, salt) — stored on-chain.
        Returns ProofOutput dict.
        """
        witness = {"secret_age": secret_age, "salt": salt}
        result = await self._run_prover("age_range", witness)

        if not self._has_binary:
            # Simulation: commitment = SHA256(age || salt)
            commitment_bytes = hashlib.sha256(
                f"{secret_age}:{salt}".encode()
            ).digest()
            result["public_inputs"]["commitment"] = commitment_bytes.hex()
            result["public_inputs"]["min_age"] = hex(min_age)
            result["public_inputs"]["max_age"] = hex(max_age)

        return result

    # ──────────────────────── Consent commitment ──────────────────────────

    async def prove_consent_commitment(
        self,
        data_type: str,
        purpose: str,
        salt: int,
        requester_id: str,
    ) -> dict:
        """
        Prove: Poseidon(data_type_hash, purpose_hash, salt, requester_id) == commitment
        without revealing data_type or purpose on-chain.

        Returns ProofOutput including commitment (stored on-chain instead of plaintext).
        """
        witness = {
            "data_type": data_type,
            "purpose": purpose,
            "salt": salt,
            "requester_id": requester_id,
        }
        result = await self._run_prover("consent_commitment", witness)

        if not self._has_binary:
            # Simulation: commitment = SHA256(data_type || purpose || salt || requester)
            commitment_bytes = hashlib.sha256(
                f"{data_type}:{purpose}:{salt}:{requester_id}".encode()
            ).digest()
            result["public_inputs"]["commitment"] = commitment_bytes.hex()
            result["public_inputs"]["requester_id"] = requester_id

        return result

    # ──────────────────────── Nullifier ───────────────────────────────────

    async def prove_nullifier(
        self,
        identity_secret: str,
        consent_id: int,
        consent_hash: str,
    ) -> dict:
        """
        Prove: SHA256(identity_secret || consent_id) == nullifier (anti-replay).

        The nullifier is stored on-chain; the same (identity_secret, consent_id)
        pair cannot generate a valid proof a second time.

        Returns ProofOutput including nullifier (stored on-chain in ConsentRecord).
        """
        witness = {
            "identity_secret": identity_secret,
            "consent_id": consent_id,
            "consent_hash": consent_hash,
        }
        result = await self._run_prover("nullifier", witness)

        if not self._has_binary:
            # Simulation: nullifier = SHA256(identity_secret || consent_id)
            identity_bytes = bytes.fromhex(identity_secret) if len(identity_secret) == 64 else identity_secret.encode()
            nullifier_bytes = hashlib.sha256(
                identity_bytes + str(consent_id).encode()
            ).digest()
            result["public_inputs"]["nullifier"] = nullifier_bytes.hex()
            result["public_inputs"]["consent_hash"] = consent_hash

        return result

    # ──────────────────────── Verification ────────────────────────────────

    async def verify_proof(self, circuit: str, proof_json: dict) -> bool:
        """
        Off-chain Groth16 verification via the gnark binary.

        Returns True if the proof is valid; False otherwise.
        In simulation mode always returns True (no real cryptographic check).
        """
        if not self._has_binary:
            logger.info("Simulation mode: skipping gnark verify for circuit=%s", circuit)
            return True

        keys_path = self.keys_dir / circuit
        if not keys_path.exists():
            logger.error("Verifying keys not found at %s", keys_path)
            return False

        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as tmp:
            json.dump(proof_json, tmp)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    str(self.binary),
                    "verify",
                    "--circuit", circuit,
                    "--proof", tmp_path,
                    "--keys-dir", str(keys_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error(
                    "gnark verify failed: stdout=%s stderr=%s",
                    result.stdout,
                    result.stderr,
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("gnark verify timed out for circuit=%s", circuit)
            return False
        finally:
            os.unlink(tmp_path)

    # ──────────────────────── Private ─────────────────────────────────────

    async def _run_prover(self, circuit: str, witness: dict) -> dict:
        """
        Invoke the gnark prover binary for `circuit` with JSON `witness`.

        Returns a ProofOutput dict with keys:
          circuit, proof, public_inputs, proof_hash, is_simulation
        """
        if not self._has_binary:
            return self._simulate(circuit, witness)

        keys_path = self.keys_dir / circuit
        if not keys_path.exists():
            logger.warning(
                "Keys for circuit %s not found at %s — falling back to simulation.",
                circuit,
                keys_path,
            )
            return self._simulate(circuit, witness)

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as out_tmp:
            out_path = out_tmp.name

        try:
            result = subprocess.run(
                [
                    str(self.binary),
                    "prove",
                    "--circuit", circuit,
                    "--witness", json.dumps(witness),
                    "--keys-dir", str(keys_path),
                    "--out", out_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.error(
                    "gnark prove failed for circuit=%s: stdout=%s stderr=%s",
                    circuit,
                    result.stdout,
                    result.stderr,
                )
                return self._simulate(circuit, witness)

            with open(out_path) as f:
                proof_output = json.load(f)

            proof_output["is_simulation"] = False
            return proof_output

        except subprocess.TimeoutExpired:
            logger.error("gnark prove timed out for circuit=%s", circuit)
            return self._simulate(circuit, witness)
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    @staticmethod
    def _simulate(circuit: str, witness: dict) -> dict:
        """
        Produce a deterministic SHA-256-based proof simulation.

        The proof_hash is SHA256(circuit || JSON(witness)) so it is
        unique per (circuit, witness) pair but carries no ZK security.
        """
        import base64

        raw = json.dumps({"circuit": circuit, **witness}, sort_keys=True).encode()
        proof_bytes = hashlib.sha256(raw).digest()
        proof_hash = hashlib.sha256(proof_bytes).hexdigest()

        return {
            "circuit": circuit,
            "proof": base64.b64encode(proof_bytes).decode(),
            "public_inputs": {},
            "proof_hash": proof_hash,
            "is_simulation": True,
        }
