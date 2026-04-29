Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py#100-100), lines 100 to 200

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#1-1), lines 1 to 100

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#100-100), lines 100 to 165

Searched for files matching `**/consent-ledger/smart_contracts/artifacts/consent_ledger/**`, 6 matches

Ran terminal command:  grep -n "grant_consent\|grantConsent\|method_selector\|selector" /home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/artifacts/consent_ledger/ConsentLedger.arc56.json | head -40

Searched for files matching `**/consent-ledger/frontend/src/contracts/**`, 3 matches

Ran terminal command:  python3 -c "
import hashlib, json

# Method signature from contract.py
sig = 'grant_consent(address,uint8[32],uint8[32],uint64,uint8)uint64'
selector = hashlib.new('sha512_256', sig.encode()).digest()[:4]
print('Contract selector:', selector.hex())

# Check what the TS client uses
import re
with open('/home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/contracts/ConsentLedgerClient.ts') as f:
    content = f.read()
# Find grantConsent method
matches = re.findall(r'grant[Cc]onsent[^\n]*', content)
for m in matches[:10]:
    print('TS:', m)
"


Ran terminal command:  grep -n "match\|label" /home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/artifacts/consent_ledger/ConsentLedger.approval.teal | head -30

Ran terminal command:  grep -n "@router.post\|@router.get" /home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py

Ran terminal command:  grep -n "@router.post" /home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py -A2

Read [](file:///home/gokulganesan/AlgoBharat/SETUP.md#1-1), lines 1 to 100

Read [](file:///home/gokulganesan/AlgoBharat/SETUP.md#100-100), lines 100 to 200

Read [](file:///home/gokulganesan/AlgoBharat/SETUP.md#200-200), lines 200 to 300

Now I have the full picture. There are **three distinct issues**:

---

## Issue 1: Deployed contract is outdated (main crash)

The TEAL error `match label2 label3 label4` shows the on-chain contract (app_id=759420732) was deployed with **3 methods**, but the current contract has **4**. The `grant_consent` selector isn't in the old routing table, so it hits `err`.

**You need to redeploy the contracts:**

```bash
cd consent-ledger

# 1. Rebuild (regenerate artifacts)
algokit project run build

# 2. Redeploy to testnet
algokit project deploy testnet
```

Then update frontend/.env with the new app IDs printed by the deploy command:
```env
VITE_APP_ID=<new ConsentLedger app_id>
VITE_APP_ADDRESS=<new ConsentLedger app_address>
VITE_ZK_VERIFIER_APP_ID=<new ZKVerifier app_id>
VITE_ORG_REGISTRY_APP_ID=<new OrgRegistry app_id>
VITE_ORG_REGISTRY_APP_ADDRESS=<new OrgRegistry app_address>
```

---

## Issue 2: Age range fails gnark constraint (age 15 < min 18)

The gnark circuit correctly rejects it — `15 ≥ 18` is false. The backend falls back to simulation (random mock), so the proof "succeeds" in the UI but that's expected demo behavior.

**Just enter an age within the form's range** (e.g. `25` for a min=18 max=120 form).

---

## Issue 3: Backend missing `/proof/set-membership` and `/proof/hash-equality`

These 404 — only `age-range`, `consent-commitment`, and `nullifier` exist in the backend. The frontend already catches the 404 and falls back to mock values, so this doesn't block the flow. But I can add stub endpoints to the backend to silence the 404: 

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py#110-110), lines 110 to 234

Replacing 4 lines with 66 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py)


```

```
Also need to add `BaseModel` — it's already imported via pydantic in the models, but let me check the imports in proof.py: 

Ran terminal command:  head -20 /home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py
Completed with input:  head -20 /home/gokulganesan/AlgoBharat/consent-ledger/backend/routers/proof.py

`BaseModel` is already imported. Now restart the backend to pick up the new endpoints:

```bash
cd consent-ledger/backend
uvicorn main:app --reload --port 8000
```

**Summary of all fixes:**

| Issue | Fix |
|---|---|
| **On-chain `err` crash** | Redeploy contracts — old testnet app has 3 methods, current code has 4. Run `algokit project run build` then `algokit project deploy testnet`, update .env with new IDs |
| **Age 15 < min 18** | Enter a valid age (e.g. `25`) — gnark correctly rejects out-of-range inputs |
| **`/proof/set-membership` 404** | Added stub endpoints for `/proof/set-membership` and `/proof/hash-equality` to the backend — restart backend to activate |

The contract redeploy is the blocking fix for the TEAL crash.

Made changes.