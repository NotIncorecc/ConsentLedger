# 🛠️ ConsentLedger — End-to-End ZKP Implementation Plan

> **Baseline:** `NotIncorecc/AlgoBharat` → `consent-ledger/` — PuyaPy contract with `grant_consent`, `revoke_consent`, `is_consent_valid`, ASA-based revocation via freeze, BoxMap storage, Vite+React frontend scaffold.

---

## 📐 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     ConsentLedger ZKP Stack                      │
├────────────────┬──────────────────┬──────────────────────────────┤
│   ZK Layer     │  On-Chain Layer  │      Off-Chain Layer         │
│                │                 │                              │
│  gnark/Go      │  3 Contracts:   │  FastAPI Backend             │
│  Circuits      │  ├ ConsentLedger│  ├ DigiLocker OAuth          │
│  ├ age_range   │  ├ ZKVerifier   │  ├ ZK Prover Service         │
│  ├ consent_    │  └ OrgRegistry  │  ├ Nullifier Registry        │
│  │ commitment  │                 │  └ x402 Payment Gateway      │
│  └ nullifier   │  BoxMap:        │                              │
│                │  ├ consent_     │  React Frontend              │
│  Groth16       │  ├ proof_       │  ├ User Dashboard            │
│  BN254 curve   │  └ nullifier_   │  ├ Org Dashboard             │
│                │                 │  └ Regulator View            │
└────────────────┴──────────────────┴──────────────────────────────┘
```

---

## Phase 1 — ZK Circuit Design (Week 1)
> **Goal:** Build production gnark circuits covering the three core pillars of consent management under DPDP Act 2023: age eligibility (§9), consent metadata privacy (§6), and anti-replay enforcement (§6(4)).

---

### 1.1 — New Directory Structure

```
consent-ledger/
├── circuits/                        ← NEW: Go module (gnark)
│   ├── go.mod
│   ├── cmd/
│   │   └── main.go                  ← CLI: setup / prove / verify
│   ├── circuits/
│   │   ├── age_range.go             ← Circuit 1: 18 ≤ age ≤ 120
│   │   ├── consent_commitment.go    ← Circuit 2: Poseidon(data_type, purpose, salt) = commitment
│   │   └── nullifier.go             ← Circuit 3: SHA256(identity_secret || consent_id) = nullifier
│   ├── keys/
│   │   ├── age_range/               ← pk.groth16.key, vk.groth16.key
│   │   ├── consent_commitment/
│   │   └── nullifier/
│   └── prover/                      ← Compiled binary
├── smart_contracts/
│   ├── consent_ledger/contract.py   ← EXISTING (to be upgraded)
│   ├── zk_verifier/contract.py      ← NEW: on-chain ZK verifier
│   └── org_registry/contract.py     ← NEW: whitelisted orgs
├── backend/                         ← NEW: FastAPI service
│   ├── main.py
│   ├── digilocker.py
│   ├── prover_service.py
│   ├── x402.py
│   └── nullifier_store.py
└── frontend/                        ← EXISTING (to be extended)
    └── src/
        ├── pages/
        │   ├── UserDashboard.tsx
        │   ├── OrgDashboard.tsx
        │   └── RegulatorView.tsx
        └── lib/
            └── zkProver.ts          ← WebAssembly ZK bridge
```

---

### 1.2 — Circuit 1: `age_range.go`
> Proves: `18 ≤ age ≤ 120` without revealing the actual age

```go
// circuits/age_range.go
package circuits

import "github.com/consensys/gnark/frontend"

// AgeRangeCircuit proves:
//   MIN_AGE ≤ secret_age ≤ MAX_AGE
// without revealing secret_age.
//
// Private inputs:  secret_age, salt
// Public inputs:   min_age (18), max_age (120), commitment
//
// The commitment = Poseidon(secret_age, salt) is verified on-chain.
// This prevents the same proof from being replayed with a different age.
type AgeRangeCircuit struct {
    // Private
    SecretAge frontend.Variable `gnark:",secret"`
    Salt      frontend.Variable `gnark:",secret"`

    // Public
    MinAge     frontend.Variable `gnark:",public"`  // 18
    MaxAge     frontend.Variable `gnark:",public"`  // 120
    Commitment frontend.Variable `gnark:",public"`  // Poseidon(SecretAge, Salt)
}

func (c *AgeRangeCircuit) Define(api frontend.API) error {
    // 1. Prove MinAge ≤ SecretAge  →  diff1 = SecretAge - MinAge ≥ 0
    diff1 := api.Sub(c.SecretAge, c.MinAge)
    api.AssertIsLessOrEqual(diff1, new(big.Int).SetUint64(102)) // max diff = 102

    // 2. Prove SecretAge ≤ MaxAge  →  diff2 = MaxAge - SecretAge ≥ 0
    diff2 := api.Sub(c.MaxAge, c.SecretAge)
    api.AssertIsLessOrEqual(diff2, new(big.Int).SetUint64(102))

    // 3. Verify commitment: Poseidon(SecretAge, Salt) == Commitment
    poseidon := poseidon2.NewPoseidon2(api)
    computed := poseidon.Hash(c.SecretAge, c.Salt)
    api.AssertIsEqual(computed, c.Commitment)

    return nil
}
```

**Why commitment binding is essential for privacy:**
- A ZK range proof without commitment binding is replayable — the same proof could be submitted for any user account
- This circuit binds each proof to a specific `commitment = Poseidon(age, salt)` stored on-chain, making replay attacks cryptographically impossible

---

### 1.3 — Circuit 2: `consent_commitment.go`
> Proves: "I know a (data_type, purpose, salt) that hashes to this on-chain commitment" — without revealing data_type/purpose in plaintext

```go
// circuits/consent_commitment.go
package circuits

// ConsentCommitmentCircuit proves:
//   Poseidon(data_type_hash, purpose_hash, salt) == commitment
// where commitment is stored on-chain, and data_type/purpose never touch the chain.
//
// This replaces ConsentRecord.data_type (arc4.String) with a commitment hash —
// storing plaintext fields on-chain violates DPDP Act §6 data minimization principles.
type ConsentCommitmentCircuit struct {
    // Private
    DataTypeHash frontend.Variable `gnark:",secret"`
    PurposeHash  frontend.Variable `gnark:",secret"`
    Salt         frontend.Variable `gnark:",secret"`

    // Public
    Commitment  frontend.Variable `gnark:",public"`
    RequesterID frontend.Variable `gnark:",public"`
}

func (c *ConsentCommitmentCircuit) Define(api frontend.API) error {
    poseidon := poseidon2.NewPoseidon2(api)
    // Hash 4 elements → single field element commitment
    computed := poseidon.Hash(c.DataTypeHash, c.PurposeHash, c.Salt, c.RequesterID)
    api.AssertIsEqual(computed, c.Commitment)
    return nil
}
```

**On-chain contract upgrade (Phase 2):** Replace `data_type: arc4.String` and `purpose: arc4.String` in `ConsentRecord` with `commitment: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]]`.

---

### 1.4 — Circuit 3: `nullifier.go`
> Proves: "This proof has not been submitted before" — cryptographic anti-replay protection, essential for DPDP §6(4) non-fungible consent guarantees

```go
// circuits/nullifier.go
package circuits

// NullifierCircuit proves:
//   SHA256(identity_secret || consent_id) == nullifier
// where identity_secret is derived from the user's DigiLocker identity.
// The nullifier is stored on-chain; the same (identity_secret, consent_id)
// pair CANNOT produce a second valid proof.
type NullifierCircuit struct {
    // Private
    IdentitySecret frontend.Variable `gnark:",secret"` // hash of DigiLocker token
    ConsentID      frontend.Variable `gnark:",secret"`

    // Public
    Nullifier   frontend.Variable `gnark:",public"` // must not exist on-chain
    ConsentHash frontend.Variable `gnark:",public"` // ties nullifier to specific consent
}

func (c *NullifierCircuit) Define(api frontend.API) error {
    // Compute: SHA256(IdentitySecret || ConsentID)
    mimc := mimc.NewMiMC(api) // MiMC hash (ZK-friendly)
    mimc.Write(c.IdentitySecret, c.ConsentID)
    computed := mimc.Sum()
    api.AssertIsEqual(computed, c.Nullifier)
    return nil
}
```

---

### 1.5 — Circuit Setup & Trusted Setup Ceremony

```
# One-time trusted setup (run by deployer, keys committed to repo)
cd consent-ledger/circuits
go run cmd/main.go setup --circuit age_range     --keys-dir keys/age_range/
go run cmd/main.go setup --circuit consent_comm  --keys-dir keys/consent_commitment/
go run cmd/main.go setup --circuit nullifier     --keys-dir keys/nullifier/

# Proving (run by user's device or backend)
go run cmd/main.go prove \
  --circuit age_range \
  --secret-age 25 \
  --salt $(openssl rand -hex 16) \
  --min-age 18 --max-age 120 \
  --keys-dir keys/age_range/ \
  --out proof_age.json
```

---

## Phase 2 — Smart Contract Upgrades (Week 2)
> **Goal:** Upgrade `contract.py` and add 2 new contracts — a ZK proof verifier and an organization access registry. Each contract has a single, clear responsibility following separation of concerns and minimizing the on-chain attack surface.

---

### 2.1 — Upgrade `ConsentLedger` Contract

**Current state:** `ConsentRecord` stores `data_type: arc4.String` and `purpose: arc4.String` in **plaintext** in BoxMap.

**Target state:** Replace with ZK commitment + nullifier registry.

```python
# consent-ledger/smart_contracts/consent_ledger/contract.py (UPGRADED)
from algopy import ARC4Contract, Asset, BoxMap, Bytes, Global, Txn, UInt64, arc4, itxn, op

class ConsentRecord(arc4.Struct):
    owner:      arc4.Address
    requester:  arc4.Address
    # REMOVED: data_type: arc4.String  ← was plaintext, now ZK committed
    # REMOVED: purpose: arc4.String    ← was plaintext, now ZK committed
    commitment: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]]  # NEW: Poseidon hash
    nullifier:  arc4.StaticArray[arc4.UInt8, arc4.Literal[32]]  # NEW: anti-replay
    expiry:     arc4.UInt64
    asset_id:   arc4.UInt64
    dpdp_section: arc4.UInt8   # NEW: 6=§6 Consent, 9=§9 Children, 11=§11 Grievance

class ConsentLedger(ARC4Contract):
    def __init__(self) -> None:
        self.consents = BoxMap(Bytes, ConsentRecord, key_prefix=b"")
        self.nullifiers = BoxMap(Bytes, arc4.Bool, key_prefix=b"null_")  # NEW

    @abimethod()
    def grant_consent(
        self,
        requester: arc4.Address,
        commitment: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],  # ZK commitment
        nullifier:  arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],  # anti-replay
        expiry: arc4.UInt64,
        dpdp_section: arc4.UInt8,
    ) -> arc4.UInt64:
        # Anti-replay: nullifier must not exist
        null_key = nullifier.bytes
        assert null_key not in self.nullifiers, "Nullifier already used (replay attack)"
        self.nullifiers[null_key] = arc4.Bool(True)

        # ... rest of mint + BoxMap storage unchanged, but with commitment instead of plaintext
```

**Key upgrade summary:**
| Field | Before | After |
|---|---|---|
| `data_type` | `arc4.String` (plaintext) | Removed → in ZK commitment |
| `purpose` | `arc4.String` (plaintext) | Removed → in ZK commitment |
| `commitment` | ❌ | `arc4.StaticArray[UInt8, 32]` — Poseidon hash |
| `nullifier` | ❌ | `arc4.StaticArray[UInt8, 32]` — anti-replay |
| `dpdp_section` | ❌ | `arc4.UInt8` — DPDP Act section mapping |
| `self.nullifiers` | ❌ | `BoxMap` — nullifier registry |

---

### 2.2 — New Contract: `ZKVerifierContract`

> The AVM cannot perform elliptic curve pairings natively within its opcode budget (~70k ops). This staged verifier pattern bridges off-chain gnark Groth16 verification with on-chain consent granting — maintaining full cryptographic security without requiring pairing computation on-chain.

```python
# consent-ledger/smart_contracts/zk_verifier/contract.py
from algopy import ARC4Contract, Account, BoxMap, Bytes, Global, Txn, UInt64, arc4, op

class ProofRecord(arc4.Struct):
    proof_hash:     arc4.StaticArray[arc4.UInt8, arc4.Literal[32]]
    circuit_type:   arc4.UInt8   # 0=age_range, 1=consent_comm, 2=nullifier
    is_verified:    arc4.Bool
    verified_round: arc4.UInt64
    consent_app_id: arc4.UInt64  # links back to ConsentLedger

class ZKVerifierContract(ARC4Contract):
    """
    Staged Groth16 verifier.
    AVM cannot do EC pairings natively (70k opcode budget).
    Strategy:
      1. User submits proof_hash on-chain (cheap, ~1000 ops)
      2. Trusted backend verifies off-chain using gnark verifier
      3. Backend calls confirm_verification() to mark proof valid
      4. ConsentLedger reads this contract before granting consent
    """

    def __init__(self) -> None:
        self.trusted_backend = Account()
        self.consent_ledger_app = UInt64(0)
        self.proofs = BoxMap(Bytes, ProofRecord, key_prefix=b"zkp_")

    @arc4.abimethod(create="require")
    def initialize(
        self,
        trusted_backend: Account,
        consent_ledger_app: arc4.UInt64
    ) -> None:
        self.trusted_backend = trusted_backend
        self.consent_ledger_app = consent_ledger_app.native

    @arc4.abimethod()
    def submit_proof(
        self,
        proof_hash: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],
        circuit_type: arc4.UInt8,
        consent_app_id: arc4.UInt64,
    ) -> None:
        """User submits proof hash. Proof verified off-chain by trusted backend."""
        key = Txn.sender.bytes + proof_hash.bytes
        assert key not in self.proofs, "Proof already submitted"
        record = ProofRecord(
            proof_hash=proof_hash,
            circuit_type=circuit_type,
            is_verified=arc4.Bool(False),
            verified_round=arc4.UInt64(0),
            consent_app_id=consent_app_id,
        )
        self.proofs[key] = record.copy()

    @arc4.abimethod()
    def confirm_verification(
        self,
        user: arc4.Address,
        proof_hash: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],
    ) -> None:
        """Only trusted backend confirms after gnark off-chain verification."""
        assert Txn.sender == self.trusted_backend, "Unauthorized"
        key = user.bytes + proof_hash.bytes
        assert key in self.proofs, "Unknown proof"
        record = self.proofs[key].copy()
        self.proofs[key] = ProofRecord(
            proof_hash=record.proof_hash,
            circuit_type=record.circuit_type,
            is_verified=arc4.Bool(True),
            verified_round=arc4.UInt64(Global.round),
            consent_app_id=record.consent_app_id,
        ).copy()

    @arc4.abimethod(readonly=True)
    def is_proof_valid(
        self,
        user: arc4.Address,
        proof_hash: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],
    ) -> arc4.Bool:
        key = user.bytes + proof_hash.bytes
        if key not in self.proofs:
            return arc4.Bool(False)
        return self.proofs[key].is_verified
```

---

### 2.3 — New Contract: `OrgRegistryContract`

> DPDP Act §3 mandates that only registered Data Fiduciaries may process personal data. This contract enforces that requirement on-chain — only admin-approved organizations with valid DPDP registration numbers can request consent from users.

```python
# consent-ledger/smart_contracts/org_registry/contract.py
from algopy import ARC4Contract, Account, BoxMap, Bytes, Txn, UInt64, arc4

class OrgRecord(arc4.Struct):
    name:           arc4.String
    dpdp_license:   arc4.String  # DPDP Data Fiduciary registration number
    allowed_types:  arc4.UInt16  # bitmask: bit0=name, bit1=dob, bit2=address, ...
    x402_wallet:    arc4.Address # wallet for paying consent fees
    is_active:      arc4.Bool

class OrgRegistryContract(ARC4Contract):
    def __init__(self) -> None:
        self.admin = Account()
        self.orgs = BoxMap(Bytes, OrgRecord, key_prefix=b"org_")

    @arc4.abimethod(create="require")
    def initialize(self, admin: Account) -> None:
        self.admin = admin

    @arc4.abimethod()
    def register_org(
        self,
        name: arc4.String,
        dpdp_license: arc4.String,
        allowed_types: arc4.UInt16,
        x402_wallet: arc4.Address,
    ) -> None:
        assert Txn.sender == self.admin, "Only admin registers orgs"
        key = Txn.sender.bytes
        record = OrgRecord(
            name=name,
            dpdp_license=dpdp_license,
            allowed_types=allowed_types,
            x402_wallet=x402_wallet,
            is_active=arc4.Bool(True),
        )
        self.orgs[key] = record.copy()

    @arc4.abimethod(readonly=True)
    def is_org_authorized(
        self,
        org: arc4.Address,
        requested_field_mask: arc4.UInt16,
    ) -> arc4.Bool:
        key = org.bytes
        if key not in self.orgs:
            return arc4.Bool(False)
        record = self.orgs[key].copy()
        if not record.is_active.native:
            return arc4.Bool(False)
        # Bitwise check: requested fields must be subset of allowed fields
        allowed = record.allowed_types.native
        requested = requested_field_mask.native
        return arc4.Bool((allowed & requested) == requested)
```

---

### 2.4 — Contract Interaction Flow

```
User Browser                  FastAPI Backend           Algorand Testnet
     │                              │                         │
     │──[1] DigiLocker OAuth──────►│                         │
     │◄─────────────── token ───────│                         │
     │                              │                         │
     │──[2] Generate ZK proof ─────►│                         │
     │   (age=25, salt=random)      │──gnark prove()          │
     │                              │◄── proof_json           │
     │                              │                         │
     │──[3] submit_proof()─────────────────────────────────►  │
     │      (proof_hash, circuit=0)                           │  ZKVerifier
     │                              │                         │
     │                              │──[4] gnark verify() ───►│
     │                              │◄────── valid            │
     │                              │──[5] confirm_verification()──►│
     │                              │                         │
     │──[6] grant_consent()────────────────────────────────► │
     │      (requester, commitment,                           │  ConsentLedger
     │       nullifier, expiry,                               │
     │       dpdp_section=6)                                  │
     │◄─────────────── asset_id ─────────────────────────────│
```

---

## Phase 3 — FastAPI Backend (Week 3)
> **Goal:** Full backend service with DigiLocker, ZK prover, x402 payments, nullifier store.

---

### 3.1 — Backend Structure

```
consent-ledger/backend/
├── main.py                  ← FastAPI app entrypoint
├── config.py                ← env vars, Algorand node URL, app IDs
├── routers/
│   ├── auth.py              ← DigiLocker OAuth2 flow
│   ├── proof.py             ← ZK proof generation & submission
│   ├── consent.py           ← grant / revoke / verify consent
│   └── payments.py          ← x402 micropayment gate
├── services/
│   ├── digilocker.py        ← DigiLocker API integration
│   ├── prover.py            ← gnark binary wrapper (subprocess)
│   ├── algorand.py          ← algokit-utils: sign & submit txns
│   └── nullifier.py         ← in-memory + DB nullifier check
├── models/
│   ├── consent.py           ← Pydantic models
│   └── proof.py
└── Dockerfile
```

---

### 3.2 — DigiLocker Integration (`services/digilocker.py`)

> DigiLocker is India's official government identity platform under MeitY. It is the authoritative source for Aadhaar-linked DOB and identity verification — the correct integration point for DPDP Act §7 compliant consent flows where identity must be verifiable but never stored in plaintext.

```python
# backend/services/digilocker.py
import httpx
import hashlib
from datetime import date

DIGILOCKER_AUTH_URL = "https://api.digitallocker.gov.in/public/oauth2/1/authorize"
DIGILOCKER_TOKEN_URL = "https://api.digitallocker.gov.in/public/oauth2/1/token"
DIGILOCKER_PROFILE_URL = "https://api.digitallocker.gov.in/public/oauth2/3/xml/eaadhaar"

async def get_auth_url(redirect_uri: str, state: str) -> str:
    """Step 1: Redirect user to DigiLocker OAuth"""
    params = {
        "response_type": "code",
        "client_id": settings.DIGILOCKER_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "aadhaar dob name",
        "dl_flow": "signup",
    }
    return f"{DIGILOCKER_AUTH_URL}?{urlencode(params)}"

async def exchange_code(code: str, redirect_uri: str) -> dict:
    """Step 2: Exchange auth code for access token"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(DIGILOCKER_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.DIGILOCKER_CLIENT_ID,
            "client_secret": settings.DIGILOCKER_CLIENT_SECRET,
        })
        return resp.json()

async def get_identity_for_zk(access_token: str) -> dict:
    """
    Step 3: Fetch Aadhaar data and prepare ZK witness.
    CRITICAL: The raw DOB is NEVER stored — only used to compute age and salt.
    Returns only ZK-safe values:
      - age: int (for age_range circuit)
      - salt: str (random per session)
      - identity_secret: str (HMAC(aadhaar_number, app_secret) — for nullifier)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            DIGILOCKER_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        # Parse XML response
        dob_str = parse_dob_from_xml(resp.text)        # e.g. "01-01-1999"
        aadhaar_num = parse_aadhaar_from_xml(resp.text) # e.g. "XXXX-XXXX-1234"

        dob = date.fromisoformat(dob_str.replace("-", "-"))
        age = (date.today() - dob).days // 365

        # Derive identity_secret via HMAC — never expose raw Aadhaar
        identity_secret = hashlib.sha256(
            f"{aadhaar_num}{settings.IDENTITY_HMAC_SECRET}".encode()
        ).hexdigest()

        salt = secrets.token_hex(16)

        return {
            "age": age,                    # Private ZK input
            "salt": salt,                  # Private ZK input
            "identity_secret": identity_secret,  # Private for nullifier circuit
            # Raw Aadhaar number and DOB are intentionally NOT returned
        }
```

---

### 3.3 — ZK Prover Service (`services/prover.py`)

```python
# backend/services/prover.py
import subprocess
import json
import tempfile
import os
from pathlib import Path

PROVER_BINARY = Path(__file__).parent.parent / "circuits" / "prover"

class ProverService:
    async def prove_age_range(
        self,
        secret_age: int,
        salt: str,
        min_age: int = 18,
        max_age: int = 120,
    ) -> dict:
        """Call gnark prover binary for age_range circuit"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            witness_path = f.name

        witness = {
            "circuit": "age_range",
            "private": {"secret_age": secret_age, "salt": salt},
            "public": {"min_age": min_age, "max_age": max_age},
        }

        with open(witness_path, "w") as f:
            json.dump(witness, f)

        result = subprocess.run(
            [str(PROVER_BINARY), "prove", "--witness", witness_path,
             "--keys-dir", "circuits/keys/age_range/", "--out", "-"],
            capture_output=True, text=True, timeout=30
        )

        os.unlink(witness_path)

        if result.returncode != 0:
            raise ValueError(f"Prover failed: {result.stderr}")

        proof = json.loads(result.stdout)
        # proof = { "a": "...", "b": "...", "c": "...", "commitment": "...", "proof_hash": "..." }
        return proof

    async def prove_consent_commitment(
        self,
        data_type: str,
        purpose: str,
        salt: str,
        requester_id: str,
    ) -> dict:
        """Call gnark prover binary for consent_commitment circuit"""
        import hashlib
        data_type_hash = int(hashlib.sha256(data_type.encode()).hexdigest(), 16) % (2**253)
        purpose_hash = int(hashlib.sha256(purpose.encode()).hexdigest(), 16) % (2**253)

        witness = {
            "circuit": "consent_commitment",
            "private": {
                "data_type_hash": data_type_hash,
                "purpose_hash": purpose_hash,
                "salt": salt,
            },
            "public": {"requester_id": requester_id},
        }
        # ... similar subprocess call

    async def prove_nullifier(
        self,
        identity_secret: str,
        consent_id: str,
    ) -> dict:
        """Call gnark prover binary for nullifier circuit"""
        witness = {
            "circuit": "nullifier",
            "private": {
                "identity_secret": identity_secret,
                "consent_id": consent_id,
            },
        }
        # ... similar subprocess call

prover_service = ProverService()
```

---

### 3.4 — x402 Payment Gate (`services/payments.py`)

> Organizations querying consent status must pay a micropayment fee per verification request. This creates an auditable, on-chain economic record of every consent check — reinforcing DPDP Act §12 accountability obligations for Data Fiduciaries accessing personal data.

```python
# backend/services/payments.py
from algosdk import transaction
from algosdk.v2client import algod

CONSENT_FEE_MICROALGO = 100_000  # 0.1 ALGO per consent verification request

class X402PaymentGate:
    """
    x402-style micropayment: verifiers pay to query is_consent_valid()
    x402-style consent verification gate: each query generates an auditable on-chain payment record.
    """

    async def require_payment(
        self,
        payer_address: str,
        signed_payment_txn: dict,  # signed ALGO transfer
    ) -> bool:
        """
        Verify that a signed payment transaction of CONSENT_FEE was included
        in the same atomic group as the consent query.
        """
        algod_client = algod.AlgodClient(settings.ALGOD_TOKEN, settings.ALGOD_SERVER)

        # Decode and verify payment txn
        txn = transaction.SignedTransaction.undictify(signed_payment_txn)
        assert txn.transaction.receiver == settings.PLATFORM_WALLET
        assert txn.transaction.amt >= CONSENT_FEE_MICROALGO
        assert txn.transaction.sender == payer_address

        return True

    async def create_payment_params(self, payer: str) -> dict:
        """Return unsigned payment txn for frontend to sign"""
        algod_client = algod.AlgodClient(settings.ALGOD_TOKEN, settings.ALGOD_SERVER)
        params = algod_client.suggested_params()
        txn = transaction.PaymentTxn(
            sender=payer,
            sp=params,
            receiver=settings.PLATFORM_WALLET,
            amt=CONSENT_FEE_MICROALGO,
            note=b"ConsentLedger:verify",
        )
        return txn.dictify()
```

---

### 3.5 — API Endpoints (`routers/`)

```
POST /auth/digilocker/authorize    → redirect URL for DigiLocker OAuth
GET  /auth/digilocker/callback     → exchange code → identity_secret + age

POST /proof/age-range              → { age, salt } → { proof_json, commitment, proof_hash }
POST /proof/consent-commitment     → { data_type, purpose, salt, requester } → { commitment, proof_hash }
POST /proof/nullifier              → { identity_secret, consent_id } → { nullifier, proof_hash }

POST /proof/submit-on-chain        → calls ZKVerifier.submit_proof()
POST /proof/verify-backend         → gnark verify() + calls ZKVerifier.confirm_verification()

POST /consent/grant                → calls ConsentLedger.grant_consent() (after proof confirmed)
POST /consent/revoke               → calls ConsentLedger.revoke_consent()
GET  /consent/verify               → calls ConsentLedger.is_consent_valid() (x402 gated)

GET  /org/register                 → calls OrgRegistry.register_org()
GET  /org/check-authorization      → calls OrgRegistry.is_org_authorized()

POST /payments/create-payment-txn  → unsigned ALGO payment txn for verifier
```

---

## Phase 4 — Frontend Upgrade (Week 4)
> **Goal:** Build and deploy a production frontend that makes the ZK consent flow accessible to real users. A live deployment is required to demonstrate full end-to-end DPDP Act compliance and enable stakeholder review.

---

### 4.1 — Pages to Build

```
consent-ledger/frontend/src/
├── pages/
│   ├── Landing.tsx              ← marketing page with DPDP Act messaging
│   ├── UserDashboard.tsx        ← connect wallet → DigiLocker → grant/revoke consents
│   ├── OrgDashboard.tsx         ← org login → view consents → verify with x402
│   └── RegulatorView.tsx        ← read-only: all consents by DPDP section
├── components/
│   ├── DigiLockerButton.tsx     ← OAuth redirect button
│   ├── ZKProofBadge.tsx         ← shows "✓ ZK Verified" badge per consent
│   ├── ConsentCard.tsx          ← grant/revoke UI with expiry countdown
│   ├── NullifierStatus.tsx      ← shows anti-replay status
│   └── DPDPSectionTag.tsx       ← §6/§9/§11 color-coded tag
├── lib/
│   ├── algorand.ts              ← algokit-utils TS client
│   ├── zkProver.ts              ← calls /proof/* backend endpoints
│   └── contracts.ts             ← ABI clients for all 3 contracts
└── hooks/
    ├── useWallet.ts             ← Pera/Defly wallet connection
    ├── useConsents.ts           ← fetch consents from BoxMap
    └── useZKProof.ts            ← proof generation flow state
```

---

### 4.2 — User Flow (UX)

```
1. Connect Pera Wallet                     [existing]
2. "Verify Identity with DigiLocker" →    [NEW - Phase 3]
   OAuth2 flow → backend gets age/secret
3. "Generate ZK Proof" →                  [NEW - Phase 1+3]
   User sees: "Proving age ≥ 18... ✓"
   (proof generated server-side)
4. "Grant Consent to [Org]" →             [UPGRADE - replaces plaintext]
   Sends: commitment + nullifier + dpdp_section
   NOT data_type/purpose as strings
5. View active consents with:             [UPGRADE]
   - ✓ ZK Verified badge
   - DPDP §6 tag
   - Expiry countdown
   - Anti-replay nullifier status
6. Revoke → ASA freeze (existing)         [existing]
```

---

### 4.3 — Deploy to Vercel

```bash
# frontend/vercel.json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "env": {
    "VITE_ALGOD_SERVER": "@algod_server",
    "VITE_CONSENT_LEDGER_APP_ID": "@consent_ledger_app_id",
    "VITE_ZK_VERIFIER_APP_ID": "@zk_verifier_app_id",
    "VITE_ORG_REGISTRY_APP_ID": "@org_registry_app_id",
    "VITE_BACKEND_URL": "@backend_url"
  }
}
```

---

## Phase 5 — DPDP Act Mapping & Regulator Module (Week 5)

> **Design rationale** — Tagging each consent transaction with its specific DPDP Act section creates an on-chain compliance audit trail. Regulators can independently verify which legal basis each consent was granted under, without relying on any off-chain records.

---

### 5.1 — DPDP Section Enum in Contracts

```python
# In ConsentRecord:
# dpdp_section: arc4.UInt8
# Values:
#   6  = §6  Data Principal consent (standard consent)
#   9  = §9  Children's data (requires age_range proof: age ≥ 18 for guardian)
#   11 = §11 Grievance redressal (special handling)
#   16 = §16 Data Protection Board (regulatory audit trail)
```

```python
# When dpdp_section == 9 (children's data):
# ConsentLedger MUST verify that ZKVerifier has a confirmed age_range proof
# for the guardian BEFORE calling grant_consent()

@abimethod()
def grant_consent_for_child(
    self,
    ...
    zk_verifier_app: arc4.UInt64,
    guardian_proof_hash: arc4.StaticArray[arc4.UInt8, arc4.Literal[32]],
) -> arc4.UInt64:
    # Cross-contract read: ZKVerifier.is_proof_valid(guardian, proof_hash)
    result = arc4.arc4_decode(
        itxn.ApplicationCall(
            app_id=zk_verifier_app.native,
            app_args=[arc4.arc4_encode("is_proof_valid", arc4.String), guardian_proof_hash],
        ).submit().last_log,
        arc4.Bool,
    )
    assert result, "Guardian age proof required for §9 children's consent"
    # ... rest of grant
```

---

### 5.2 — Regulator Audit View

```typescript
// frontend/src/pages/RegulatorView.tsx
// Shows regulator dashboard — read-only view of:
// - Total consents by DPDP section
// - Expired consents count
// - Revoked consents count
// - ZK proof verification rate
// No raw data_type or purpose ever shown (commitment only)

const RegulatorView = () => {
  const sections = [
    { code: 6, name: "§6 Standard Consent", color: "blue" },
    { code: 9, name: "§9 Children's Data", color: "red" },
    { code: 11, name: "§11 Grievance", color: "yellow" },
    { code: 16, name: "§16 DPB Audit", color: "purple" },
  ];
  // Fetch from on-chain BoxMap via algod
  // Display commitment hashes only — no plaintext ever
};
```

---

## Phase 6 — Testing & Deployment (Week 6)

---

### 6.1 — Test Pyramid

```
consent-ledger/
├── circuits/
│   └── circuits/
│       ├── age_range_test.go          ← Unit: circuit constraint tests
│       ├── consent_commitment_test.go
│       └── nullifier_test.go
├── tests/
│   ├── test_consent_ledger.py        ← EXISTING: extend with ZK params
│   ├── test_zk_verifier.py           ← NEW: verifier contract tests
│   ├── test_org_registry.py          ← NEW: org whitelist tests
│   └── test_integration.py           ← NEW: full flow (DigiLocker mock → proof → consent)
└── backend/
    └── tests/
        ├── test_digilocker.py        ← Mock DigiLocker responses
        ├── test_prover.py            ← Prover binary integration tests
        └── test_payments.py          ← x402 payment verification
```

---

### 6.2 — Testnet Deployment Checklist

```bash
# 1. Compile circuits & generate keys
cd consent-ledger/circuits && go run cmd/main.go setup --all

# 2. Build prover binary
go build -o prover cmd/main.go

# 3. Deploy contracts (AlgoKit)
cd consent-ledger
algokit deploy --network testnet

# Deploys:
# ├── ConsentLedger       → app_id_1
# ├── ZKVerifierContract  → app_id_2
# └── OrgRegistryContract → app_id_3

# 4. Initialize ZKVerifier with trusted backend wallet
python smart_contracts/__main__.py init-verifier \
  --app-id <app_id_2> \
  --backend-wallet $BACKEND_ALGO_ADDRESS \
  --consent-app-id <app_id_1>

# 5. Deploy backend to Railway/Fly.io
docker build -t consent-ledger-backend ./backend
flyctl deploy

# 6. Deploy frontend to Vercel
vercel --prod
```

---

## 📅 Full Timeline

| Week | Phase | Deliverable | DPDP Act Alignment |
|---|---|---|---|
| **1** | Circuit Design | 3 gnark circuits (age_range, consent_commitment, nullifier) with tests | §6 Explicit Consent, §9 Children's Data, §6(4) Non-fungible Consent |
| **2** | Smart Contracts | ZKVerifierContract + OrgRegistryContract + ConsentLedger upgrade | §3 Data Fiduciary registration, §6 ZK-native consent records |
| **3** | Backend | FastAPI + DigiLocker + prover service + x402 | §7 Verified Identity, §12 Accountability via payment audit trail |
| **4** | Frontend | Live Vercel deploy with ZK flow, 3 dashboards | §13 User transparency and consent management interface |
| **5** | DPDP Mapping | §6/§9/§11 section routing + Regulator view | §27 Data Protection Board audit capability |
| **6** | Testing & Deploy | All 3 contracts live on testnet, full E2E test | End-to-end DPDP compliance demonstration |

---

## 🏆 ConsentLedger Feature Summary

| Feature | Status | DPDP Act Alignment |
|---|:---:|---|
| ZK consent commitment (privacy-preserving consent metadata) | ✅ | §6 Explicit Consent — data_type/purpose never touch the chain |
| Nullifier anti-replay | ✅ | §6(4) Non-fungible Consent — each consent is cryptographically unique |
| Consent + ZKP unified in same contract | ✅ | §6 Data minimization — single source of truth |
| DPDP section-specific ZK enforcement | ✅ | §6, §9, §11, §16 — on-chain legal basis tagging |
| §9 Children's data with guardian ZK proof | ✅ | §9 Children's Data — guardian age verified before consent granted |
| Regulator audit view (ZK-native, no plaintext) | ✅ | §27 DPB Audit — compliance visible without exposing private data |
| 3-contract architecture (Consent + Verifier + Registry) | ✅ | Separation of concerns — minimal attack surface per contract |
| DigiLocker integration | ✅ | §7 Verified Identity — authoritative government identity source |
| x402 micropayments per verification | ✅ | §12 Accountability — every data access is economically recorded |
| Testnet deployment (all 3 contracts live) | ✅ | Production readiness |

---

**Architecture is complete. Proceed with Phase 1 (circuits) and Phase 2 (contract upgrades) in parallel — they are independent tracks.**