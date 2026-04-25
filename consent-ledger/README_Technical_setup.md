# ConsentLedger

A decentralised consent management system built on Algorand. Users grant data-access consent as on-chain NFT tokens stored in AVM box storage; organisations verify consent status in real time; users can revoke consent by freezing the token — all without a central authority.

---

## Quick Start — TestNet Setup (Step-by-Step)

Follow these steps in order to get the project running on Algorand TestNet from scratch.

---

### Prerequisites

Install each tool and verify it is on your `PATH`:

| Tool | Min version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://www.python.org/downloads/) or `pyenv install 3.12` |
| pipx | any | `pip install pipx && pipx ensurepath` |
| AlgoKit CLI | 2.10 | `pipx install algokit` |
| Poetry | 1.2+ | `pipx install poetry` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) or `nvm install --lts` |
| Docker Desktop | any | [docker.com](https://www.docker.com/) *(optional — only needed for LocalNet)* |

```bash
# Verify all tools are installed
algokit --version   # expect 2.10.x
python3 --version   # expect 3.12.x
poetry --version    # expect 1.2+
node --version      # expect v18+
npm --version
```

---

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd consent-ledger
```

---

### Step 2 — Install Python dependencies

```bash
poetry install
```

This creates a `.venv` inside the project with `algokit-utils`, `puyapy`, `algorand-python-testing`, and `python-dotenv`.

---

### Step 3 — Run unit tests (optional, no network needed)

```bash
poetry run pytest tests/ -v
```

All tests should pass in under a second. This validates the contract logic locally before deploying.

---

### Step 4 — Generate a deployer wallet

Run this one-liner to create a fresh Algorand account:

```bash
poetry run python - <<'EOF'
import algosdk
pk, addr = algosdk.account.generate_account()
print("Address :", addr)
print("Mnemonic:", algosdk.mnemonic.from_private_key(pk))
EOF
```

**Save both outputs.** You will need the mnemonic in Step 6 and the address in Step 5.

---

### Step 5 — Fund the deployer wallet

1. Copy the **Address** printed in Step 4.
2. Go to the [Algorand TestNet Dispenser](https://dispenser.testnet.aws.algodev.network/).
3. Paste your address and request **5 ALGO**.

> The deploy script automatically sends **1 ALGO** to the contract account to cover box storage MBR.

Wait ~5 seconds for the transaction to confirm, then verify the balance at [testnet.explorer.perawallet.app](https://testnet.explorer.perawallet.app).

---

### Step 6 — Create the contract environment file

Create a file at `consent-ledger/.env` (in the project root, **not** inside `frontend/`):

```env
ALGOD_SERVER=https://testnet-api.4160.nodely.dev
ALGOD_PORT=443
ALGOD_TOKEN=
INDEXER_SERVER=https://testnet-idx.4160.nodely.dev
INDEXER_PORT=443
INDEXER_TOKEN=
DEPLOYER_MNEMONIC=<your 25-word mnemonic from Step 4>
```

> **Never commit this file.** It is already in `.gitignore`.

---

### Step 7 — Build the smart contract

```bash
algokit project run build
```

This compiles `smart_contracts/consent_ledger/contract.py` to TEAL bytecode and regenerates the ABI artifacts in `smart_contracts/artifacts/consent_ledger/`.

---

### Step 8 — Deploy to TestNet

```bash
algokit project deploy testnet
```

The command reads your `.env`, connects to the Algorand TestNet via the Nodely public API, and deploys the contract. Look for output like:

```
ConsentLedger deployed: app_id=759250014, app_address=D432YBOLKEK5C4VKKVIFFXT2EBENZYRE32OBTYSOOMRUGLJY6GMV2ZTE74
```

**Copy the `app_id` and `app_address` — you need them in the next step.**

> If you redeploy after a contract change, `on_update=AppendApp` creates a new app version. Always update `frontend/.env` with the latest values.

---

### Step 9 — Configure the frontend

Create a file at `consent-ledger/frontend/.env`:

```env
VITE_APP_ID=<app_id from Step 8>
VITE_APP_ADDRESS=<app_address from Step 8>
```

---

### Step 10 — Install frontend dependencies

```bash
cd frontend
npm install
```

---

### Step 11 — Start the dev server

```bash
npm run dev
```

Open the URL shown in the terminal (default: [http://localhost:5173](http://localhost:5173)).

---

### Step 12 — Connect Pera Wallet and use the app

Install the [Pera Wallet browser extension](https://chromewebstore.google.com/detail/pera-wallet/eanbowmgkkphaenmcaldejakbdopdnak) (or use the mobile app). **Switch Pera to TestNet mode** before connecting.

#### Grant consent (data owner / user)

1. Click **Connect Pera Wallet** in the header → approve in Pera.
2. Select the **User** role.
3. Go to the **Grant Consent** tab.
4. Fill in:
   - **Requester Algorand Address** — the organisation's 58-character TestNet address
   - **Data Type** — KYC / Medical / Financial
   - **Purpose** — free-text description
   - **Expiry** — optional date; leave blank for no expiry
5. Click **Grant Consent** → approve the transaction in Pera Wallet.

#### Revoke consent (data owner)

1. Go to **My Consents** — your issued tokens load automatically.
2. Active tokens show a green **Active** badge.
3. Click **Revoke** → approve in Pera Wallet. The token is frozen on-chain immediately.

#### View granted consents (organisation)

1. Connect the **organisation's wallet** in Pera.
2. Select the **Organisation** role.
3. Go to **Granted to Me** — all consents where your address is the authorised requester appear.

---

## Rebuilding after contract changes

If you modify `smart_contracts/consent_ledger/contract.py`:

```bash
# 1. Recompile and regenerate ABI artifacts
algokit project run build

# 2. Redeploy to TestNet (creates a new app version)
algokit project deploy testnet

# 3. Regenerate the TypeScript client from the new ABI
algokit generate client \
  smart_contracts/artifacts/consent_ledger/ConsentLedger.arc56.json \
  --output frontend/src/contracts/ConsentLedgerClient.ts

# 4. Update frontend/.env with the new app_id and app_address
```

---

## Project structure

```
consent-ledger/
├── smart_contracts/
│   ├── consent_ledger/
│   │   ├── contract.py          # Algorand Python smart contract (PuyaPy)
│   │   └── deploy_config.py     # Deploy script (reads .env)
│   └── artifacts/
│       └── consent_ledger/
│           ├── ConsentLedger.arc56.json   # ABI specification
│           └── consent_ledger_client.py   # Auto-generated Python client
├── tests/
│   └── test_consent_ledger_unit.py        # Offline unit tests
├── frontend/
│   ├── .env                               # VITE_APP_ID / VITE_APP_ADDRESS
│   └── src/
│       ├── contracts/
│       │   └── ConsentLedgerClient.ts     # Auto-generated TypeScript client
│       ├── components/
│       │   ├── GrantConsentForm.tsx        # Grant consent view
│       │   ├── ActiveConsents.tsx          # My Consents view (data owner)
│       │   ├── OrgConsents.tsx             # Org View (organisation)
│       │   └── Header.tsx
│       ├── config.ts                       # Reads VITE_APP_ID / VITE_APP_ADDRESS
│       └── utils.ts                        # Box decoder, address helpers
├── .env                                    # Contract deploy secrets (do not commit)
├── pyproject.toml
└── poetry.toml
```

---

## How the box key works

Each consent record is stored in AVM box storage with a **72-byte key**:

```
"consent_" (8 bytes) + owner_pubkey (32 bytes) + requester_pubkey (32 bytes)
```

The key is fully deterministic from `owner address + requester address`, so the box reference can always be declared in the transaction before it executes — no simulation race conditions.

