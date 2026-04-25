prompt:
restart the docker containers, create a step-by-step readme file so that I can initialize this project on the testnet

working:

Ran terminal command:  cd /home/gokulganesan/AlgoBharat/consent-ledger && algokit localnet start 2>&1 | tail -20
Completed with input:  cd /home/gokulganesan/AlgoBharat/consent-ledger && algokit localnet start 2>&1 | tail -20

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#1-1), lines 1 to 80

Ran terminal command:  algokit localnet reset 2>&1 | tail -20
Completed with input:  algokit localnet reset 2>&1 | tail -20

LocalNet is running. Now let me read the full existing README and the project's env/config files to write an accurate README:  

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#80-80), lines 80 to 200

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/config.ts)

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#200-200), lines 200 to 280

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/deploy_config.py)

Searched for files matching `**/consent-ledger/algokit.toml`, no matches

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/pyproject.toml)

Ran terminal command:  ls /home/gokulganesan/AlgoBharat/consent-ledger/.env* 2>/dev/null && cat /home/gokulganesan/AlgoBharat/consent-ledger/.env 2>/dev/null | grep -v MNEMONIC

Searched for files matching `**/consent-ledger/.env*`, no matches

Ran terminal command:  cat /home/gokulganesan/AlgoBharat/consent-ledger/.env.testnet 2>/dev/null

Ran terminal command:  cat /home/gokulganesan/AlgoBharat/consent-ledger/frontend/.env 2>/dev/null

Now I have everything I need. Let me overwrite the README with a clean, accurate step-by-step guide: 

Replacing 3 lines with 263 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md)


```

```
Now trim the old content that follows (the legacy AlgoKit-generated boilerplate): 

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#30-30), lines 30 to 170

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#100-100), lines 100 to 390

The README has duplicated old content at the bottom. Let me find the exact line where the old content starts and truncate it: 

Ran terminal command:  grep -n "## How it works" /home/gokulganesan/AlgoBharat/consent-ledger/README.md

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/README.md#258-258), lines 258 to 270

Ran terminal command:  wc -l /home/gokulganesan/AlgoBharat/consent-ledger/README.md

Ran terminal command:  head -264 /home/gokulganesan/AlgoBharat/consent-ledger/README.md > /tmp/readme_clean.md && mv /tmp/readme_clean.md /home/gokulganesan/AlgoBharat/consent-ledger/README.md

Ran terminal command:  wc -l /home/gokulganesan/AlgoBharat/consent-ledger/README.md && tail -5 /home/gokulganesan/AlgoBharat/consent-ledger/README.md

Done. Here's a summary of what was done:

**Docker containers** — `algokit localnet reset` successfully restarted all 4 containers (`algod`, `postgres`, `conduit`, `indexer`).

**README** — rewritten at README.md with 12 numbered steps:

| Step | What it covers |
|---|---|
| Prerequisites | Tool versions + install commands |
| 1 | Clone the repo |
| 2 | `poetry install` |
| 3 | Run unit tests offline |
| 4 | Generate a deployer wallet (one-liner script) |
| 5 | Fund it via TestNet dispenser |
| 6 | Create .env with API endpoints + mnemonic |
| 7 | `algokit project run build` |
| 8 | `algokit project deploy testnet` → copy `app_id` / `app_address` |
| 9 | Create `frontend/.env` with the values from Step 8 |
| 10 | `npm install` |
| 11 | `npm run dev` |
| 12 | Pera Wallet setup + how to grant/revoke/view consents |

Plus a **Rebuilding after contract changes** section and **Project structure** tree at the end.

Made changes.