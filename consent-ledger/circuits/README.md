# ConsentLedger ZK Circuits (Phase 1)

This directory contains the **gnark Groth16** zero-knowledge circuits for the ConsentLedger system.

## Architecture

Three circuits implement privacy-preserving consent management under DPDP Act 2023:

| Circuit | Purpose | DPDP Relevance |
|---|---|---|
| `age_range` | Proves 18 ≤ age ≤ 120 without revealing DOB | §9 Children's Data |
| `consent_commitment` | Proves knowledge of (data_type, purpose, salt) behind on-chain hash | §6 Explicit Consent |
| `nullifier` | Anti-replay proof: MiMC(identity_secret, consent_id) = nullifier | §6(4) Non-fungible Consent |

## Design Advantages

| Feature | Status | Rationale |
|---|:---:|---|
| Commitment binding (anti-replay) | ✅ | Proof is tied to `Poseidon(secret, salt)` on-chain — cannot be reused across users |
| Private consent metadata | ✅ | data_type/purpose never stored on-chain — only ZK commitment hash |
| Nullifier registry | ✅ | MiMC(identity_secret, consent_id) stored on-chain prevents double-submission |
| 3 domain-specific circuits | ✅ | Each circuit maps to a specific DPDP Act obligation (§9, §6, §6(4)) |

## Quick Start

### Prerequisites

```bash
go 1.22+
```

### Step 1: Trusted Setup (one-time, run by deployer)

```bash
cd consent-ledger/circuits

# Compile circuits and generate proving/verifying keys
go run cmd/main.go setup --circuit age_range          --keys-dir keys/age_range/
go run cmd/main.go setup --circuit consent_commitment --keys-dir keys/consent_commitment/
go run cmd/main.go setup --circuit nullifier          --keys-dir keys/nullifier/
```

### Step 2: Generate a Proof

```bash
# Prove user is 18-120 years old (without revealing age)
go run cmd/main.go prove \
  --circuit age_range \
  --witness '{"secret_age": 25, "salt": 123456789}' \
  --keys-dir keys/age_range/ \
  --out proof_age.json

# Prove consent metadata commitment (without revealing data_type/purpose)
go run cmd/main.go prove \
  --circuit consent_commitment \
  --witness '{"data_type":"health_data","purpose":"insurance","salt":987654,"requester_id":"ABCDEF1234..."}' \
  --keys-dir keys/consent_commitment/ \
  --out proof_consent.json

# Prove nullifier (anti-replay)
go run cmd/main.go prove \
  --circuit nullifier \
  --witness '{"identity_secret":"deadbeef...","consent_id":42,"consent_hash":"aabbcc..."}' \
  --keys-dir keys/nullifier/ \
  --out proof_null.json
```

### Step 3: Verify a Proof

```bash
go run cmd/main.go verify \
  --circuit age_range \
  --proof proof_age.json \
  --keys-dir keys/age_range/
```

### Step 4: Run Tests

```bash
go test ./circuits/... -v -timeout 120s
```

## Proof JSON Format

```json
{
  "circuit": "age_range",
  "proof": "<base64-encoded Groth16 proof bytes>",
  "public_inputs": {
    "commitment": "0xdeadbeef..."
  },
  "proof_hash": "<sha256 of proof bytes — submitted to ZKVerifierContract>"
}
```

The `proof_hash` is what gets submitted to the `ZKVerifierContract.submit_proof()` method on Algorand. The backend then verifies the full proof off-chain and calls `confirm_verification()`.

## Circuit Constraint Counts (approximate, BN254 Groth16)

| Circuit | Constraints | Proving Time |
|---|---|---|
| `age_range` | ~500 | ~0.5s |
| `consent_commitment` | ~300 | ~0.3s |
| `nullifier` | ~250 | ~0.3s |

## Directory Structure

```
circuits/
├── go.mod
├── README.md
├── cmd/
│   └── main.go          ← CLI: setup / prove / verify
├── circuits/
│   ├── age_range.go     ← Circuit 1: age range proof
│   ├── consent_commitment.go  ← Circuit 2: private consent metadata
│   ├── nullifier.go     ← Circuit 3: anti-replay nullifier
│   └── *_test.go        ← Unit tests for each circuit
└── keys/
    ├── age_range/        ← pk.groth16.key, vk.groth16.key (after setup)
    ├── consent_commitment/
    └── nullifier/
```
