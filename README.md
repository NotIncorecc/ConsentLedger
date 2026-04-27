# ConsentLedger
Decentralized consent management on Algorand — where your permission to share data is a blockchain asset you hold, control, and can revoke in seconds.

## The problem today
Consent is a checkbox buried in a terms page — stored in an organization's database, invisible to the user
Revoking access means calling a helpline or sending a request that may take days — or never happen
No tamper-proof audit trail — organizations can claim consent existed without proof

## What ConsentLedger does
Consent is minted as an ASA — a token in your wallet. You hold it. Nobody can forge or delete it.
Revoke means freeze — one transaction, confirmed in under 4 seconds, permanently on-chain
Every grant, revoke, and access attempt is immutably logged and auditable by regulators

<img width="781" height="314" alt="image" src="https://github.com/user-attachments/assets/af031788-620b-44ec-a693-3bedb91e4753" />

## ConsentLedger in one page
— the problem, the solution, the flow, and the scale of why it matters.
The core tension it captures is this: data consent in India today is a legal fiction. Organizations collect it, store it in their own systems, and there is no mechanism for a user to actually verify it existed, check its scope, or enforce its removal. ConsentLedger makes consent into a physical object — a blockchain asset — that lives in the user's wallet, not the organization's database. The user owns the proof of their own permission. That is the shift.

Upvote the project on DoraHacks
https://dorahacks.io/buidl/43102

All three Phase 2 contracts are live on testnet:

| Contract | App ID | App Address |
|---|---|---|
| **ConsentLedger** (upgraded) | `759443293` | `2FN6S5JJ...` |
| **ZKVerifierContract** | `759443440` | `THKQ6UTU...` |
| **OrgRegistryContract** | `759443291` | `LVQLVHAV...` |

You can inspect them on [lora.algokit.io/testnet](https://lora.algokit.io/testnet) by searching those app IDs.
