The backend is fine now. The error is purely the **on-chain contract** — app `759420732` is an old deployment. The TEAL routing table at pc=56 only has 3 method labels (`label2 label3 label4`) so `grant_consent` hits `err`.

Let me check what's needed to redeploy: 

Ran terminal command:  ls /home/gokulganesan/AlgoBharat/consent-ledger/.env* 2>/dev/null && cat /home/gokulganesan/AlgoBharat/consent-ledger/.env 2>/dev/null | grep -v MNEMONIC
Completed with input:  ls /home/gokulganesan/AlgoBharat/consent-ledger/.env* 2>/dev/null && cat /home/gokulganesan/AlgoBharat/consent-ledger/.env 2>/dev/null | grep -v MNEMONIC

Ran terminal command:  cat /home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/deploy_config.py

Ran terminal command:  cat /home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/zk_verifier/deploy_config.py && echo "---" && cat /home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/org_registry/deploy_config.py

Ran terminal command:  cat .algokit.toml | grep -A5 "build\|deploy"

Good. The deploy uses `OnUpdate.AppendApp` — it creates a **new** app every time rather than updating in-place. You simply need to run the deploy and paste the new IDs into the .env.

Run these two commands in the consent-ledger terminal:

**Step 1 — Build (regenerate artifacts):**
```bash
cd /home/gokulganesan/AlgoBharat/consent-ledger
algokit project run build
```

**Step 2 — Deploy to testnet:**
```bash
algokit project deploy testnet
```

The output will look like:
```
ConsentLedger deployed: app_id=76XXXXXXX, app_address=AAAA...
ZKVerifierContract deployed: app_id=76XXXXXXX, app_address=BBBB...
OrgRegistryContract deployed: app_id=76XXXXXXX, app_address=CCCC...
```

**Step 3 — Paste the new IDs into the frontend .env:**

Open frontend/.env and update these 5 values with whatever was printed:
```env
VITE_APP_ID=<new ConsentLedger app_id>
VITE_APP_ADDRESS=<new ConsentLedger app_address>
VITE_ZK_VERIFIER_APP_ID=<new ZKVerifier app_id>
VITE_ORG_REGISTRY_APP_ID=<new OrgRegistry app_id>
VITE_ORG_REGISTRY_APP_ADDRESS=<new OrgRegistry app_address>
```

**Step 4 — Fund the new ConsentLedger address** (it needs ALGO for MBR to create boxes + mint ASAs):
Use the [TestNet Dispenser](https://dispenser.testnet.aws.algodev.network/) with the new `app_address`, request at least 2 ALGO.

**Step 5 — Restart the Vite dev server** (so it picks up the new `VITE_APP_ID`):
```bash
cd consent-ledger/frontend && npm run dev
```

The root cause is that `OnUpdate.AppendApp` never replaces the old app — it always creates a fresh one, so the old app_id in your .env points to an outdated TEAL program.