Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#1-1), lines 1 to 150

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range.go)

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/consent_commitment.go)

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier.go)

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#80-80), lines 80 to 140

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#1-1), lines 1 to 150

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#175-175), lines 175 to 175

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#150-150), lines 150 to 350

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#350-350), lines 350 to 500

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/tests/test_consent_ledger_unit.py#1-1), lines 1 to 80

Now I have enough context. Let me give you a thorough, structured explanation of everything.

---

# ConsentLedger — Complete Technical Deep Dive

---

## 1. What We've Built (The Big Picture)

ConsentLedger is a **decentralized consent management system** for India's DPDP (Digital Personal Data Protection) Act. The idea: when a hospital asks for your medical records, you give cryptographic consent on a public blockchain — but *what* you consented to is never visible on-chain. Only a hash of it is. You can also prove you're 18+ without revealing your actual age.

The system has three layers:

```
Go ZK Circuits  →  Algorand Smart Contracts  →  React Frontend
(prove privately)   (store & verify on-chain)    (user interface)
```

---

## 2. What Are Smart Contracts?

A **smart contract** is a program that runs *inside* a blockchain. Nobody can change its logic after deployment. When you call it, every validator node runs the exact same code and reaches the same result — this is what makes it trustless.

On Algorand, smart contracts are called **AVM Applications** (Algorand Virtual Machine). You write them in Python (PuyaPy) or TypeScript (PuyaTs), then the Puya compiler translates them to **TEAL bytecode** — Algorand's own instruction set.

### What we built — `ConsentLedger` contract (contract.py)

```
class ConsentRecord(arc4.Struct):
    owner:     arc4.Address   ← Aadhaar user's wallet
    requester: arc4.Address   ← Hospital/org wallet
    data_type: arc4.String    ← "medical_records"
    purpose:   arc4.String    ← "annual health screening"
    expiry:    arc4.UInt64    ← Unix timestamp
    asset_id:  arc4.UInt64   ← ASA token ID
```

Three methods:

| Method | What it does |
|---|---|
| `grant_consent()` | Mints an ASA (NFT) + stores record in BoxMap |
| `revoke_consent()` | Freezes that ASA (on-chain revocation proof) |
| `is_consent_valid()` | Read-only check: is the ASA unfrozen + not expired? |

The contract is ~200 lines of Python, compiled by the Puya compiler to TEAL, and runs on every Algorand node.

---

## 3. Algorand Transactions — How They Work

Algorand has several transaction types, and this project uses most of them:

### 3.1 Payment Transaction
The most basic: send ALGO (Algorand's native currency) from A to B. Every contract call requires a fee (typically 0.001 ALGO) paid via a payment transaction attached to the call.

### 3.2 Application Call Transaction (what we send to call the contract)
```
Txn.sender = user's wallet
app_id = ConsentLedger's deployed app ID
app_args = ["grant_consent", requester_address, "medical_records", ...]
```
When you call `grant_consent()`, you send an Application Call transaction. The AVM receives it, runs the TEAL code, and if it succeeds, the state changes are committed.

### 3.3 Inner Transactions (the contract creates these itself)
Inside `grant_consent()`, the smart contract itself creates sub-transactions using `itxn`:

```python
# Inside grant_consent() — the contract mints an ASA:
mint_result = itxn.AssetConfig(
    total=1,          # only 1 token (NFT-style)
    decimals=0,
    unit_name=b"CONSENT",
    manager=Global.current_application_address,   # the CONTRACT owns it
    freeze=Global.current_application_address,    # the CONTRACT can freeze it
    clawback=Global.current_application_address,  # the CONTRACT can take it back
).submit()
```

This is an **inner transaction** — a transaction spawned *by the contract* inside the same block. The contract sets itself as the `freeze` authority, which is how revocation works.

### 3.4 Asset Freeze Transaction (revocation)
```python
# Inside revoke_consent() — the contract freezes its own ASA:
itxn.AssetFreeze(
    freeze_asset=Asset(native_asset_id),
    freeze_account=Global.current_application_address,
    frozen=True,
).submit()
```
Freezing an ASA means nobody can transfer it. This is the on-chain signal for "consent revoked." Any verifier calling `is_consent_valid()` checks the frozen flag.

### 3.5 `is_consent_valid()` — a "simulate" / dry-run call
This is marked `readonly=True` which maps to an AVM **simulate** call — it reads state without modifying anything, costs no fees, and can be called by any third party to check if consent is still active.

---

## 4. How We Actually Implemented ZK in Go

This is the most complex part. The entire ZK system lives in circuits.

### 4.1 What is a ZK Proof?

A Zero-Knowledge Proof lets you prove a statement is true **without revealing the underlying data**. Example: "I am over 18" without showing your date of birth.

Mathematically, you're proving: *"I know secret values X such that f(X) = Y"* where Y is public, X is private, and f is your circuit.

### 4.2 The ZK Stack We Used

| Component | What it is | Our choice |
|---|---|---|
| ZK proof system | The cryptographic protocol | **Groth16** |
| Elliptic curve | The math field everything lives in | **BN254** (aka alt-bn128) |
| ZK-friendly hash | Hash function that works inside circuits | **MiMC** |
| Circuit framework | Go library for writing circuits | **gnark** (by ConsenSys) |

**Why Groth16?** It produces tiny proofs (192 bytes) that verify very fast. The downside is it needs a "trusted setup" ceremony per circuit — we run this once and commit the keys to the repo. The proof has three elliptic curve points: `A, B, C`.

**Why BN254?** It supports efficient pairing operations needed by Groth16. It's the same curve Ethereum uses for its ZK precompiles.

**Why MiMC?** Regular hash functions (SHA256, Keccak) are very expensive inside ZK circuits because they have lots of bit operations. MiMC is designed for the BN254 field — it uses only multiplication and addition, which are cheap in R1CS.

### 4.3 What is R1CS?

**Rank-1 Constraint System** — the internal representation of your circuit. Every `api.AssertIsEqual()`, `api.Sub()`, and range check you write gets compiled into polynomial constraints:

```
(a · b) = c    for each constraint
```

gnark compiles your Go `Define()` function into a list of these constraints. The Groth16 prover then finds values satisfying all of them.

### 4.4 Circuit 1: Age Range — circuits/circuits/age_range.go

**Statement to prove:** "I know a secret age where 18 ≤ age ≤ 120, and this commitment = MiMC(age, salt)"

```go
func (c *AgeRangeCircuit) Define(api frontend.API) error {
    rc := rangecheck.New(api)

    diff1 := api.Sub(c.SecretAge, AgeMin)   // = age - 18
    rc.Check(diff1, AgeRangeBits)            // proves diff1 ≥ 0 (i.e., age ≥ 18)

    diff2 := api.Sub(AgeMax, c.SecretAge)   // = 120 - age
    rc.Check(diff2, AgeRangeBits)            // proves diff2 ≥ 0 (i.e., age ≤ 120)

    h, _ := mimc.NewMiMC(api)
    h.Write(c.SecretAge, c.Salt)
    api.AssertIsEqual(h.Sum(), c.Commitment) // proves commitment is correct
    return nil
}
```

**The `rangecheck`** works by decomposing the number into bits and constraining each bit to be 0 or 1. If `diff1` has 7 bits (0–127), and we also know diff1 ≤ 102 (because diff2 ≥ 0), then age is definitely in [18, 120].

**The commitment** is the key: `Commitment = MiMC(SecretAge, Salt)`. This 32-byte value is stored on-chain. The proof is only valid for someone who knows the specific `(age, salt)` pair that produced that commitment — no replay attacks.

**Private inputs:** `SecretAge, Salt` — never leave the user's machine  
**Public inputs:** `Commitment` — stored on Algorand blockchain

### 4.5 Circuit 2: Consent Commitment — circuits/circuits/consent_commitment.go

**Statement to prove:** "I know the actual (data_type, purpose, salt) behind this on-chain commitment"

```go
func (c *ConsentCommitmentCircuit) Define(api frontend.API) error {
    h, _ := mimc.NewMiMC(api)
    h.Write(c.DataTypeHash, c.PurposeHash, c.Salt, c.RequesterID)
    api.AssertIsEqual(h.Sum(), c.Commitment)
    return nil
}
```

Instead of storing `"medical_records"` in plaintext (visible to everyone on-chain), we store `MiMC("medical_records_hash", "health_screening_hash", salt, requester_id)`. When a verifier needs to confirm what was consented to, the user reveals the pre-image off-chain. Nothing sensitive ever touches the blockchain.

### 4.6 Circuit 3: Nullifier — circuits/circuits/nullifier.go

**Statement to prove:** "I am the specific user with this identity secret, and I haven't submitted this consent before"

```go
func (c *NullifierCircuit) Define(api frontend.API) error {
    h, _ := mimc.NewMiMC(api)
    h.Write(c.IdentitySecret, c.ConsentID)
    api.AssertIsEqual(h.Sum(), c.Nullifier)
    return nil
}
```

`IdentitySecret = HMAC(aadhaar_number, app_secret)` — derived from DigiLocker, never stored. `Nullifier = MiMC(IdentitySecret, ConsentID)` is stored in the contract's `nullifiers` BoxMap. If the same user tries to submit the same consent twice, the nullifier already exists on-chain → transaction reverts. This is the same mechanism Tornado Cash uses to prevent double-spending.

### 4.7 The CLI Flow — circuits/cmd/main.go

The Go CLI has three subcommands:

**`setup`** — Trusted setup ceremony (run once):
1. Compiles your Go circuit into R1CS constraints
2. Runs Groth16 trusted setup using BN254
3. Writes `pk.groth16.key` (proving key, ~50MB) and `vk.groth16.key` (verifying key, ~1KB) to disk

```bash
go run cmd/main.go setup --circuit age_range --keys-dir keys/age_range/
```

**`prove`** — Generate a proof:
1. Takes private witness JSON: `{"secret_age": 25, "salt": 123456}`
2. Computes commitment: `MiMC(25, 123456)` in native BN254 field arithmetic
3. Loads proving key
4. Calls `groth16.Prove()` — this takes ~1–2 seconds
5. Outputs a `proof.json` with the 192-byte proof + public inputs + `SHA256(proof_bytes)` as `proof_hash`

**`verify`** — Verify a proof:
1. Loads verifying key
2. Rebuilds public witness from `proof.json`
3. Calls `groth16.Verify()` — takes ~10ms
4. Outputs `VALID` or `INVALID`

---

## 5. Blockchain Concepts Used

### 5.1 ASA — Algorand Standard Asset
Every consent is represented as an **NFT** (1 unit, 0 decimals). The blockchain natively tracks who holds it and whether it's frozen. This gives us:
- A unique, immutable ID per consent (`asset_id`)
- Built-in freeze mechanism for revocation
- No custom token accounting code needed

### 5.2 BoxMap — On-Chain Key-Value Storage
Algorand has a storage primitive called **boxes** — arbitrary byte arrays stored permanently next to an application. We use `BoxMap(Bytes, ConsentRecord)` keyed by `owner_address(32 bytes) || requester_address(32 bytes)`.

```python
box_key = Txn.sender.bytes + requester.bytes  # 64-byte key
self.consents[box_key] = record.copy()
```

Each box has a per-byte rent cost (~0.0025 ALGO per byte), paid by whoever creates the box. Boxes survive block-to-block unless explicitly deleted.

### 5.3 ARC-4 — ABI Standard
ARC-4 is Algorand's equivalent of Ethereum's ABI encoding. The `@abimethod()` decorator marks a Python function as a callable ABI method. The Puya compiler generates a method selector hash (first 4 bytes of `SHA512/256(method_signature)`) that clients use to route calls. The ConsentLedgerClient.ts frontend file is auto-generated from the ARC-56 JSON spec and handles all encoding/decoding.

### 5.4 Global Transaction Context (`Txn`, `Global`)
Inside a contract, `Txn.sender` is the authenticated caller — you cannot spoof it. `Global.current_application_address` is the contract's own deterministically derived address. These are part of the AVM's execution environment.

### 5.5 Inner Transactions (`itxn`)
Contracts can spawn sub-transactions that execute atomically. In our case, `grant_consent()` spawns an `AssetConfig` inner transaction to mint the ASA, all in the same atomic block. If the consent storage fails, the ASA minting is also reverted.

### 5.6 Trusted Setup (ZK-specific blockchain concept)
Groth16 requires a one-time **trusted setup** ceremony that produces structured reference string parameters. These are committed to the repo and anyone can verify they're correct. This is equivalent to what Zcash did with their "Powers of Tau" ceremony.

### 5.7 Commitment Scheme
A cryptographic commitment `C = Hash(secret, randomness)` is:
- **Hiding:** C reveals nothing about `secret`
- **Binding:** You can't find a different `secret'` that gives the same C

We use this three ways:
- Age commitment: binds proof to user's actual age
- Consent commitment: hides data_type/purpose on-chain
- Nullifier: binds identity to a specific consent (anti-replay)

### 5.8 Nullifier Pattern (anti-double-spend)
Borrowed from private cryptocurrency design (Zcash, Tornado Cash). Each proof produces a unique nullifier. Once spent/submitted on-chain, the nullifier is recorded. Any second attempt with the same identity+consent pair produces the same nullifier → rejected. This gives us non-transferable, non-reusable consent.

---

## 6. Current vs. Planned State

| Component | Status |
|---|---|
| `ConsentLedger` contract with ASA-based consent | **Built & tested** |
| Unit tests with `algopy_testing` | **Built** |
| 3 gnark ZK circuits (age_range, consent_commitment, nullifier) | **Built** |
| CLI for setup/prove/verify | **Built** |
| React frontend scaffold | **Built** |
| ZKVerifierContract, OrgRegistryContract | **Planned (Phase 2)** |
| FastAPI backend + DigiLocker | **Planned (Phase 3)** |
| Plaintext → commitment upgrade in ConsentRecord | **Planned (Phase 2)** |

The ZK layer (Go) and the contract layer (Python) are currently independent — the planned upgrade in Phase 2 will wire them together by replacing `data_type: arc4.String` with `commitment: arc4.StaticArray[arc4.UInt8, Literal[32]]` in `ConsentRecord`.