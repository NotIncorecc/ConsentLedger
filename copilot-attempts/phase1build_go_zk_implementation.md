Let me read the full MASTER_ROADMAP.md and the existing contract code to understand the complete picture before implementing.  

Read [](file:///home/gokulganesan/AlgoBharat/MASTER_ROADMAP.md#1-1), lines 1 to 100

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#1-1), lines 1 to 100

Read [](file:///home/gokulganesan/AlgoBharat/MASTER_ROADMAP.md#100-100), lines 100 to 200

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/smart_contracts/consent_ledger/contract.py#100-100), lines 100 to 175

Ran terminal command:  go version && which go
Completed with input:  go version && which go

Read [](file:///home/gokulganesan/AlgoBharat/MASTER_ROADMAP.md#200-200), lines 200 to 300

Ran terminal command:  ls /usr/local/go/bin/go 2>/dev/null || ls ~/go/bin/go 2>/dev/null || apt list --installed 2>/dev/null | grep golang | head -5

Ran terminal command:  find /usr /home -name "go" -type f 2>/dev/null | head -5; echo "---"; ls /snap/bin/go 2>/dev/null; echo "done"

Checked terminal output

Ran terminal command:  echo $PATH && ls /usr/local/ 2>/dev/null
Completed with input:  echo $PATH && ls /usr/local/ 2>/dev/null

Created 8 todos

Ran terminal command:  curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz -o /tmp/go.tar.gz && sudo tar -C /usr/local -xzf /tmp/go.tar.gz && echo "Go installed successfully"

Go is downloading in the background. Let me start creating all the circuit files in parallel. 

Starting: *Create circuits directory structure* (2/8)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/go.mod)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/doc.go)

Now create the three circuits: 

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range.go)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/consent_commitment.go)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier.go)

Now write the test files: 

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/consent_commitment_test.go)

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier_test.go)

Now write the CLI (`cmd/main.go`): 

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go)

Now create placeholder key directories and a README: 

Created [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/README.md)

Ran terminal command:  mkdir -p /home/gokulganesan/AlgoBharat/consent-ledger/circuits/keys/{age_range,consent_commitment,nullifier} && touch /home/gokulganesan/AlgoBharat/consent-ledger/circuits/keys/age_range/.gitkeep && touch /home/gokulganesan/AlgoBharat/consent-ledger/circuits/keys/consent_commitment/.gitkeep && touch /home/gokulganesan/AlgoBharat/consent-ledger/circuits/keys/nullifier/.gitkeep && echo "Directories created"

Now check if Go installation finished: 

Checked terminal output

Go is installed. Now run `go mod tidy` to pull all dependencies: 

Starting: *Run go mod tidy & verify compilation* (8/8)

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go version && go mod tidy 2>&1

Checked terminal output

Checked terminal output

`go mod tidy` completed. Now check for compilation errors: 

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go build ./... 2>&1

Let me check the actual file and fix the compilation errors:  

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#1-1), lines 1 to 50

The file has a duplicate `package cmd` at the top inserted automatically. Let me fix it: 

Replacing 2 lines with 1 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go)


```

```
Also fix the `groth16.NewCS` — re-compile the circuit in prove instead of loading R1CS from disk: 

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#140-140), lines 140 to 210

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#210-210), lines 210 to 260

I need to fix the `groth16.NewCS` call — re-compile the circuit instead:  

Replacing 31 lines with 25 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go)


```

```
Also remove the unused R1CS file write in setup and the `ccsPath` reference:  

Replacing 22 lines with 15 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go)


```

```
Also fix the verify command to re-compile instead of loading R1CS. Let me check the verify section:   

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/cmd/main.go#270-270), lines 270 to 330

The verify command is fine. Now try building again:  

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go build ./... 2>&1

Checked terminal output

Clean build — no errors. Now run the circuit tests:   

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go test ./circuits/... -v -timeout 300s -run TestAgeRangeCircuit_SatisfyingWitness 2>&1

Same issue with test files - duplicate package declaration. Let me check and fix all three test files:    

Ran terminal command:  head -5 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go && echo "---" && head -5 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/consent_commitment_test.go && echo "---" && head -5 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier_test.go

Replacing 2 lines with 1 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go)


```

```
Also check/fix the circuits/doc.go:   

Ran terminal command:  head -5 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/doc.go

Ran terminal command:  head -3 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range.go && echo "---" && head -3 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/consent_commitment.go && echo "---" && head -3 /home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier.go

Good. Now run the tests again:   

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go test ./circuits/... -v -timeout 300s -run "TestAgeRangeCircuit_SatisfyingWitness|TestConsentCommitmentCircuit_SaltUniqueness|TestNullifierCircuit_DifferentConsentSameIdentity" 2>&1

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier_test.go#135-135), lines 135 to 155

The issue is hex literals overflowing `int64`. Fix the nullifier tests:   

Replacing 19 lines with 19 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/nullifier_test.go)


```

```
Also fix the age_range test that uses `frontend.Variable` directly:  

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go#133-133), lines 133 to 145

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go#155-155), lines 155 to 175

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go#175-175), lines 175 to 192

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/circuits/circuits/age_range_test.go#1-1), lines 1 to 20

Good, imports look fine. Now run the fast tests again:    

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go test ./circuits/... -v -timeout 300s -run "TestAgeRangeCircuit_SatisfyingWitness|TestConsentCommitmentCircuit_SaltUniqueness|TestNullifierCircuit_DifferentConsentSameIdentity" 2>&1

All 3 circuits pass. Now run the full Groth16 proof tests (including reject/fail cases):    

Ran terminal command:  export PATH=$PATH:/usr/local/go/bin && cd /home/gokulganesan/AlgoBharat/consent-ledger/circuits && go test ./circuits/... -v -timeout 600s -run "TestAgeRangeCircuit_ValidAge|TestAgeRangeCircuit_UnderageMinor|TestAgeRangeCircuit_WrongCommitment|TestNullifierCircuit_Valid|TestNullifierCircuit_WrongNullifier|TestNullifierCircuit_Replay|TestConsentCommitmentCircuit_Valid|TestConsentCommitmentCircuit_WrongRequester" 2>&1

**All 8 tests pass** including both valid and invalid witness cases. Let me update the todos and mark Phase 1 complete:  

Continue to iterate?
[object Object]

Made changes.

Completed: *Run go mod tidy & verify compilation* (8/8)

Phase 1 is complete. Here's what was built:

---

## Phase 1 — Done ✓

**New directory:** circuits

### 3 gnark Groth16 ZK Circuits (BN254)

| Circuit | File | What it proves | DPDP relevance |
|---|---|---|---|
| `AgeRangeCircuit` | circuits/age_range.go | `18 ≤ secret_age ≤ 120` + commitment binding | §9 Children's Data |
| `ConsentCommitmentCircuit` | circuits/consent_commitment.go | `MiMC(data_type, purpose, salt, requester) = commitment` | §6 Explicit Consent |
| `NullifierCircuit` | circuits/nullifier.go | `MiMC(identity_secret, consent_id) = nullifier` — anti-replay | §6(4) Non-fungible Consent |

### Tests (all passing)
- 8 tests verified: valid witnesses succeed, invalid witnesses fail (age < 18, wrong commitment, replayed nullifier, wrong requester)
- Tests validate both the cryptographic constraints AND the DPDP business logic

### CLI (`cmd/main.go`)
3 subcommands: `setup` (trusted setup + save keys), `prove` (generate Groth16 proof → JSON), `verify` (verify proof + hash integrity check)

### Why commitment binding matters
A ZK circuit without commitment binding is replayable — the same proof works for any user account.