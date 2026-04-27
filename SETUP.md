# ConsentLedger — Setup Guide

Full setup guide for running ConsentLedger locally and deploying to Algorand TestNet.
Follow the sections in sequence: ZK Circuits → Smart Contracts → Backend → Frontend.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [ZK Circuits (gnark)](#1-zk-circuits-gnark)
4. [Smart Contracts](#2-smart-contracts)
5. [Backend (FastAPI)](#3-backend-fastapi)
6. [Frontend (React + Vite)](#4-frontend-react--vite)
7. [Running the Full Stack](#5-running-the-full-stack)
8. [Environment Variables Reference](#6-environment-variables-reference)
9. [Wallets & TestNet](#7-wallets--testnet)

---

## Prerequisites

Install all tools and verify they are on your `PATH` before proceeding.

| Tool | Min version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://python.org) or `pyenv install 3.12` |
| pipx | any | `pip install pipx && pipx ensurepath` |
| AlgoKit CLI | 2.10 | `pipx install algokit` |
| Poetry | 1.2+ | `pipx install poetry` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) or `nvm install --lts` |
| Go | 1.22+ | [go.dev/dl](https://go.dev/dl) |
| Docker Desktop | any | [docker.com](https://docker.com) *(optional — LocalNet only)* |

```bash
# Verify
algokit --version   # 2.10.x
python3 --version   # 3.12.x
poetry --version    # 1.x
node --version      # v18+
go version          # go1.22+
```

---

## Project Structure

```
AlgoBharat/
└── consent-ledger/                  # Monorepo root (AlgoKit project)
    ├── .algokit.toml                # AlgoKit project config & run commands
    ├── .env                         # Contract deployer secrets (gitignored)
    ├── .env.testnet                 # TestNet node endpoints
    ├── pyproject.toml               # Python project / Poetry config
    │
    ├── smart_contracts/             # Algorand Python (PuyaPy) contracts
    │   ├── consent_ledger/          # Phase 1+2 — core consent NFT contract
    │   │   ├── contract.py          # ConsentLedgerContract: grant/revoke consent
    │   │   └── deploy_config.py     # Deployment script
    │   ├── zk_verifier/             # Phase 2 — on-chain gnark proof verifier
    │   │   ├── contract.py          # ZKVerifierContract: submit_proof, confirm_verification
    │   │   └── deploy_config.py
    │   ├── org_registry/            # Phase 2 — whitelisted organisation registry
    │   │   ├── contract.py          # OrgRegistryContract: register_org, is_org_authorized
    │   │   └── deploy_config.py
    │   └── artifacts/               # Auto-generated ABI + TEAL (do not hand-edit)
    │       ├── consent_ledger/      # consent_ledger.arc56.json + .teal files
    │       ├── zk_verifier/
    │       └── org_registry/
    │
    ├── circuits/                    # gnark Groth16 ZK circuits (Go)
    │   ├── go.mod
    │   ├── cmd/main.go              # CLI: setup, prove, verify
    │   ├── circuits/
    │   │   ├── age_range.go         # Proves 18 ≤ age ≤ 120 (DPDP §9)
    │   │   ├── consent_commitment.go # Proves knowledge of commitment preimage (§6)
    │   │   └── nullifier.go         # Anti-replay: MiMC(identity_secret, consent_id)
    │   └── keys/                    # Trusted setup output (proving + verifying keys)
    │       ├── age_range/
    │       ├── consent_commitment/
    │       └── nullifier/
    │
    ├── backend/                     # FastAPI ZK prover service
    │   ├── main.py                  # App entrypoint + CORS config
    │   ├── config.py                # Pydantic settings (reads .env)
    │   ├── requirements.txt
    │   ├── routers/
    │   │   ├── auth.py              # DigiLocker OAuth2 flow
    │   │   ├── proof.py             # POST /proof/age-range, /proof/consent-commitment …
    │   │   ├── consent.py           # GET/POST /consent/* (x402-gated)
    │   │   └── payments.py          # x402 payment helpers
    │   ├── services/
    │   │   ├── algorand.py          # AlgoSDK helpers (sign, send, read state)
    │   │   ├── prover.py            # Calls gnark prover binary / simulation fallback
    │   │   ├── nullifier.py         # Nullifier derivation + registry check
    │   │   └── digilocker.py        # DigiLocker API client
    │   └── models/
    │       ├── consent.py           # Pydantic request/response models
    │       └── proof.py
    │
    ├── frontend/                    # React 19 + Vite + Tailwind dApp
    │   ├── package.json
    │   ├── vite.config.ts
    │   ├── .env                     # Vite env vars (VITE_APP_ID, etc.) — gitignored
    │   └── src/
    │       ├── App.tsx              # Root: role picker + routing
    │       ├── config.ts            # Reads VITE_* env vars
    │       ├── utils.ts             # ConsentRecord decoder + helpers
    │       ├── lib/
    │       │   ├── circuitRegistry.ts  # Circuit library, form templates, DPDP metadata
    │       │   └── zkProver.ts         # API client for FastAPI proof endpoints
    │       ├── contracts/           # Auto-generated typed ABI clients
    │       │   ├── ConsentLedgerClient.ts
    │       │   ├── ZKVerifierClient.ts
    │       │   └── OrgRegistryClient.ts
    │       └── components/
    │           ├── RolePicker.tsx      # Landing: User / Org / Regulator selector
    │           ├── Header.tsx          # Nav tabs + wallet connect
    │           ├── ZKConsentFlow.tsx   # 4-step user consent wizard (identity→form→prove→submit)
    │           ├── ActiveConsents.tsx  # User's issued consent tokens
    │           ├── OrgConsents.tsx     # Org view: consents granted to their address
    │           ├── OrgFormBuilder.tsx  # Org circuit form designer
    │           ├── RegulatorView.tsx   # DPDP section audit dashboard (read-only)
    │           ├── ConsentCard.tsx     # Shared consent record card w/ ZK badges
    │           ├── DPDPSectionTag.tsx  # DPDP Act section pill badge
    │           ├── ZKProofBadge.tsx    # "ZK Verified" / "Pending Proof" badge
    │           ├── NullifierStatus.tsx # Anti-replay nullifier display
    │           └── DigiLockerButton.tsx # DigiLocker OAuth trigger
    │
    └── tests/                       # Pytest unit tests (no network required)
        ├── test_consent_ledger_unit.py
        ├── test_org_registry_unit.py
        └── test_zk_verifier_unit.py
```

---

## 1. ZK Circuits (gnark)

The ZK circuits are written in Go using the gnark library. They must be compiled and their trusted setup must be run before the backend can generate proofs.

### 1a. Install Go dependencies

```bash
cd consent-ledger/circuits
go mod download
```

### 1b. Run trusted setup (one-time per circuit)

This generates proving and verifying keys in `circuits/keys/`. Run once — or whenever a circuit changes.

```bash
cd consent-ledger/circuits

go run cmd/main.go setup --circuit age_range          --keys-dir keys/age_range/
go run cmd/main.go setup --circuit consent_commitment --keys-dir keys/consent_commitment/
go run cmd/main.go setup --circuit nullifier          --keys-dir keys/nullifier/
```

> **This step takes 1-3 minutes** per circuit on a modern laptop.

### 1c. (Optional) Run circuit tests

```bash
go test ./circuits/... -v
```

### 1d. Build the prover binary

The backend calls this binary to generate proofs. Build it once and place it where `config.py` expects it (`../circuits/prover` relative to the backend directory).

```bash
cd consent-ledger/circuits
go build -o prover ./cmd/
# Output: consent-ledger/circuits/prover
```

> **Simulation fallback:** If the binary is absent, the backend falls back to random mock proofs for development/demo. The frontend also has its own in-browser mock fallback.

---

## 2. Smart Contracts

### 2a. Install Python dependencies

```bash
cd consent-ledger
poetry install
```

### 2b. Run unit tests (no network required)

```bash
poetry run pytest tests/ -v
```

All tests should pass in under 2 seconds.

### 2c. Generate a deployer wallet

```bash
poetry run python - <<'EOF'
import algosdk
pk, addr = algosdk.account.generate_account()
print("Address :", addr)
print("Mnemonic:", algosdk.mnemonic.from_private_key(pk))
EOF
```

Save both values. The mnemonic goes into `.env` (Step 2e). The address is funded in Step 2d.

### 2d. Fund the deployer on TestNet

1. Copy the **Address** from Step 2c.
2. Open the [TestNet Dispenser](https://dispenser.testnet.aws.algodev.network/).
3. Paste the address and request **5 ALGO**.
4. Verify at [testnet.explorer.perawallet.app](https://testnet.explorer.perawallet.app).

### 2e. Create the contract environment file

Create `consent-ledger/.env`:

```env
# Algorand TestNet node (public, no token required)
ALGOD_SERVER=https://testnet-api.4160.nodely.dev
ALGOD_PORT=443
ALGOD_TOKEN=

INDEXER_SERVER=https://testnet-idx.4160.nodely.dev
INDEXER_PORT=443
INDEXER_TOKEN=

# Deployer wallet (from Step 2c) — NEVER commit this
DEPLOYER_MNEMONIC=<your 25-word mnemonic>
```

### 2f. Build the contracts

```bash
cd consent-ledger
algokit project run build
```

This compiles all three PuyaPy contracts to TEAL bytecode and regenerates `smart_contracts/artifacts/`.

### 2g. Deploy to TestNet

```bash
algokit project deploy testnet
```

Expected output (app IDs will differ):

```
ConsentLedgerContract deployed: app_id=759443293, app_address=ABCD...
ZKVerifierContract    deployed: app_id=759443440, app_address=EFGH...
OrgRegistryContract   deployed: app_id=759443291, app_address=IJKL...
```

**Copy all three `app_id` values — you need them in Step 3 and Step 4.**

### 2h. Regenerate typed frontend clients

If contracts change after initial deployment, regenerate the TypeScript clients:

```bash
cd consent-ledger

algokit generate client \
  smart_contracts/artifacts/consent_ledger/ConsentLedger.arc56.json \
  --language typescript \
  --output frontend/src/contracts/ConsentLedgerClient.ts

algokit generate client \
  smart_contracts/artifacts/zk_verifier/ZKVerifierContract.arc56.json \
  --language typescript \
  --output frontend/src/contracts/ZKVerifierClient.ts

algokit generate client \
  smart_contracts/artifacts/org_registry/OrgRegistryContract.arc56.json \
  --language typescript \
  --output frontend/src/contracts/OrgRegistryClient.ts
```

---

## 3. Backend (FastAPI)

The backend exposes ZK proof generation, DigiLocker OAuth, and org-management endpoints. It runs as a standalone uvicorn server.

### 3a. Install backend dependencies

```bash
cd consent-ledger/backend
pip install -r requirements.txt
```

Or use the project-level Poetry virtualenv:

```bash
cd consent-ledger
poetry install   # already done in Step 2a
```

### 3b. Create the backend environment file

Create `consent-ledger/backend/.env`:

```env
# Algorand node
ALGOD_SERVER=https://testnet-api.algonode.cloud
ALGOD_PORT=443
ALGOD_TOKEN=

INDEXER_SERVER=https://testnet-idx.algonode.cloud
INDEXER_PORT=443
INDEXER_TOKEN=

# Deployer mnemonic (same as Step 2e — used to sign on-chain proof confirmations)
DEPLOYER_MNEMONIC=<your 25-word mnemonic>

# Deployed app IDs (from Step 2g)
CONSENT_LEDGER_APP_ID=759443293
ZK_VERIFIER_APP_ID=759443440
ORG_REGISTRY_APP_ID=759443291

# DigiLocker OAuth (leave blank for demo/simulation mode)
DIGILOCKER_CLIENT_ID=
DIGILOCKER_CLIENT_SECRET=
DIGILOCKER_REDIRECT_URI=http://localhost:8000/auth/digilocker/callback

# ZK prover binary (from Step 1d). Blank = simulation mode.
PROVER_BINARY=../circuits/prover
PROVER_KEYS_DIR=../circuits/keys

# Security (change in production)
APP_SECRET=consent-ledger-dev-secret-change-in-production
JWT_SECRET=consent-ledger-jwt-secret-change-in-production
```

### 3c. Start the backend server

```bash
cd consent-ledger/backend
uvicorn main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`.

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/digilocker/authorize` | Start DigiLocker OAuth flow |
| `GET` | `/auth/digilocker/callback` | OAuth2 callback |
| `POST` | `/proof/age-range` | Generate age range ZK proof |
| `POST` | `/proof/consent-commitment` | Generate consent commitment proof |
| `POST` | `/proof/set-membership` | Generate blood group / set membership proof |
| `POST` | `/proof/hash-equality` | Generate document hash equality proof |
| `POST` | `/proof/submit-on-chain` | Submit proof to ZKVerifierContract |
| `GET` | `/consent/{owner}/{requester}` | Verify consent status (x402-gated) |

---

## 4. Frontend (React + Vite)

### 4a. Install frontend dependencies

```bash
cd consent-ledger/frontend
npm install
```

### 4b. Create the frontend environment file

Create `consent-ledger/frontend/.env`:

```env
# ConsentLedger app IDs (from Step 2g)
VITE_APP_ID=759443293
VITE_APP_ADDRESS=<ConsentLedger app_address from Step 2g>
VITE_ZK_VERIFIER_APP_ID=759443440
VITE_ORG_REGISTRY_APP_ID=759443291
VITE_ORG_REGISTRY_APP_ADDRESS=<OrgRegistry app_address from Step 2g>

# FastAPI backend (Step 3)
VITE_BACKEND_URL=http://localhost:8000

# DigiLocker redirect (must match backend config)
VITE_DIGILOCKER_REDIRECT_URI=http://localhost:8000/auth/digilocker/callback
```

### 4c. Start the dev server

```bash
cd consent-ledger/frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4d. Build for production

```bash
npm run build
# Output: frontend/dist/
```

---

## 5. Running the Full Stack

Open **four terminal windows** in order:

```
Terminal 1 — Backend
─────────────────────────────────────
cd consent-ledger/backend
uvicorn main:app --reload --port 8000

Terminal 2 — Frontend
─────────────────────────────────────
cd consent-ledger/frontend
npm run dev

Terminal 3 — (optional) LocalNet
─────────────────────────────────────
algokit localnet start

Terminal 4 — (optional) Watch logs
─────────────────────────────────────
tail -f consent-ledger/backend/logs/* 2>/dev/null || true
```

Once both servers are running, open [http://localhost:5173](http://localhost:5173).

### App Roles

| Role | Who uses it | What they can do |
|---|---|---|
| **User** | Data owner (patient, citizen) | Complete 4-step ZK consent flow, view and revoke issued tokens |
| **Organisation** | Hospital, clinic, fintech | View consents granted to their address, design ZK circuit forms via Form Builder |
| **Regulator** | Data Protection Board | Read-only audit dashboard: consent stats by DPDP Act section, ZK commitment audit trail |

### ZK Consent Flow (User)

1. **Identity** — Connect Pera Wallet, optionally verify via DigiLocker OAuth
2. **Form** — Enter org address, pick form template, fill ZK circuit inputs (age, blood group, document hash)
3. **Prove** — Backend generates Groth16 proofs per field (or mock proofs in demo mode)
4. **Submit** — `grantConsent(requester, commitment[32], nullifier[32], expiry, dpdp_section)` sent on-chain; ASA consent token minted

---

## 6. Environment Variables Reference

### `consent-ledger/.env` (contract deployer)

| Variable | Required | Description |
|---|---|---|
| `ALGOD_SERVER` | Yes | Algorand node URL |
| `ALGOD_PORT` | Yes | Node port (443 for HTTPS) |
| `ALGOD_TOKEN` | No | Empty for public nodes |
| `INDEXER_SERVER` | Yes | Indexer URL |
| `DEPLOYER_MNEMONIC` | Yes | 25-word mnemonic for the deployer account |

### `consent-ledger/backend/.env`

| Variable | Default | Description |
|---|---|---|
| `CONSENT_LEDGER_APP_ID` | `759443293` | ConsentLedger app ID on TestNet |
| `ZK_VERIFIER_APP_ID` | `759443440` | ZKVerifier app ID |
| `ORG_REGISTRY_APP_ID` | `759443291` | OrgRegistry app ID |
| `DEPLOYER_MNEMONIC` | — | Signs `confirm_verification()` calls |
| `DIGILOCKER_CLIENT_ID` | — | DigiLocker app credential (blank = demo mode) |
| `DIGILOCKER_CLIENT_SECRET` | — | DigiLocker app secret |
| `PROVER_BINARY` | `../circuits/prover` | Path to gnark prover binary (blank = simulation) |
| `PROVER_KEYS_DIR` | `../circuits/keys` | Path to trusted setup keys |
| `APP_SECRET` | dev value | HMAC key for identity secret derivation |
| `JWT_SECRET` | dev value | Session JWT signing key |

### `consent-ledger/frontend/.env`

| Variable | Description |
|---|---|
| `VITE_APP_ID` | ConsentLedger app ID |
| `VITE_APP_ADDRESS` | ConsentLedger app address |
| `VITE_ZK_VERIFIER_APP_ID` | ZKVerifier app ID |
| `VITE_ORG_REGISTRY_APP_ID` | OrgRegistry app ID |
| `VITE_ORG_REGISTRY_APP_ADDRESS` | OrgRegistry app address |
| `VITE_BACKEND_URL` | FastAPI server base URL (default: `http://localhost:8000`) |
| `VITE_DIGILOCKER_REDIRECT_URI` | Must match backend `DIGILOCKER_REDIRECT_URI` |

---

## 7. Wallets & TestNet

### Get a TestNet wallet

1. Install [Pera Wallet](https://perawallet.app) (browser extension or mobile).
2. In Pera settings, switch network to **TestNet**.
3. Fund the account at [dispenser.testnet.aws.algodev.network](https://dispenser.testnet.aws.algodev.network).

### Useful TestNet explorers

- Transactions & accounts: [testnet.explorer.perawallet.app](https://testnet.explorer.perawallet.app)
- App state & boxes: [lora.algokit.io/testnet](https://lora.algokit.io/testnet)
- Debug traces: `algokit explore` (opens Lora automatically)

### LocalNet (fully offline, no tokens needed)

```bash
algokit localnet start          # Start Docker-based LocalNet
algokit localnet status         # Check status
algokit localnet reset          # Reset to genesis if something is broken
algokit project deploy localnet # Deploy to LocalNet instead of TestNet
algokit localnet stop           # Stop when done
```

> For LocalNet, set `ALGOD_SERVER=http://localhost` and `ALGOD_PORT=4001` with `ALGOD_TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.

---

## Common Issues

| Problem | Fix |
|---|---|
| `algokit project run build` fails | Ensure Poetry venv is active: `poetry shell` first |
| `Buffer is not defined` in frontend | Expected — generated clients use `// @ts-nocheck`, runs fine in browser |
| Backend returns mock proofs | Either no prover binary or `PROVER_BINARY` path is wrong — demo mode is intentional |
| Pera wallet not connecting | Ensure Pera is set to **TestNet** and you are on `localhost:5173` |
| `insufficient balance` on grant | Fund the wallet with at least 1 ALGO from the dispenser |
| Box storage error | The contract needs a 0.0025 ALGO MBR per box — the deploy script seeds 1 ALGO to the app account |
| DigiLocker returns error | Normal — leave `DIGILOCKER_CLIENT_ID` blank for demo mode; the app uses a mock identity secret |
