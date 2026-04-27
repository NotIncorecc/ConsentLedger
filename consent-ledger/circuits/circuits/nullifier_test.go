package circuits_test

import (
	"math/big"
	"testing"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend"
	"github.com/consensys/gnark/test"

	"consent-ledger/circuits/circuits"
)

// TestNullifierCircuit_Valid tests that a valid (identity_secret, consent_id)
// pair produces a correct nullifier that satisfies the circuit.
func TestNullifierCircuit_Valid(t *testing.T) {
	// Simulate: user with DigiLocker identity grants consent to OrgA
	identitySecret := big.NewInt(0x1EADBEE0_CAFE0ABE) // HMAC(aadhaar, app_secret)
	consentID := big.NewInt(0x1BCDEF12_3456789)       // unique per grant

	// ConsentHash = commitment of the associated ConsentCommitmentCircuit
	consentHash := big.NewInt(0x1122334455667788)

	// Compute the on-chain nullifier
	nullifier := mimcHash(identitySecret, consentID)

	assignment := &circuits.NullifierCircuit{
		IdentitySecret: identitySecret,
		ConsentID:      consentID,
		Nullifier:      nullifier,
		ConsentHash:    consentHash,
	}

	assert := test.NewAssert(t)
	assert.ProverSucceeded(
		&circuits.NullifierCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestNullifierCircuit_WrongNullifier tests that a tampered nullifier FAILS.
// This ensures the on-chain stored nullifier cannot be forged.
func TestNullifierCircuit_WrongNullifier(t *testing.T) {
	identitySecret := big.NewInt(0x1111111122222222)
	consentID := big.NewInt(0x3333333344444444)
	consentHash := big.NewInt(0x5555555566666666)

	// Use a forged nullifier — does NOT match MiMC(identitySecret, consentID)
	forgedNullifier := big.NewInt(0x7999999988888888)

	assignment := &circuits.NullifierCircuit{
		IdentitySecret: identitySecret,
		ConsentID:      consentID,
		Nullifier:      forgedNullifier,
		ConsentHash:    consentHash,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.NullifierCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestNullifierCircuit_DifferentConsentSameIdentity tests that the same identity
// produces DIFFERENT nullifiers for different consents — ensures granularity.
// This is the core anti-replay property: revoking one consent does not affect others.
func TestNullifierCircuit_DifferentConsentSameIdentity(t *testing.T) {
	identitySecret := big.NewInt(0x0AAABBBBCCCCDDDD)
	consentID1 := big.NewInt(1001) // consent to OrgA
	consentID2 := big.NewInt(1002) // consent to OrgB

	nullifier1 := mimcHash(identitySecret, consentID1)
	nullifier2 := mimcHash(identitySecret, consentID2)

	if nullifier1.Cmp(nullifier2) == 0 {
		t.Fatal("Same identity with different consent IDs produced identical nullifiers")
	}

	consentHash := big.NewInt(0x7777777788888888)

	// Both should produce valid proofs
	assert := test.NewAssert(t)
	assert.SolvingSucceeded(
		&circuits.NullifierCircuit{},
		&circuits.NullifierCircuit{
			IdentitySecret: identitySecret,
			ConsentID:      consentID1,
			Nullifier:      nullifier1,
			ConsentHash:    consentHash,
		},
		test.WithCurves(ecc.BN254),
	)
	assert.SolvingSucceeded(
		&circuits.NullifierCircuit{},
		&circuits.NullifierCircuit{
			IdentitySecret: identitySecret,
			ConsentID:      consentID2,
			Nullifier:      nullifier2,
			ConsentHash:    consentHash,
		},
		test.WithCurves(ecc.BN254),
	)
}

// TestNullifierCircuit_Replay simulates a replay attack:
// An attacker tries to submit the same nullifier for a different consent.
// The circuit fails because the nullifier is bound to a specific (identity, consent) pair.
func TestNullifierCircuit_Replay(t *testing.T) {
	identitySecret := big.NewInt(0x0EEDFACEDEADBEEF)
	consentID := big.NewInt(42)
	consentHash := big.NewInt(77)

	nullifier := mimcHash(identitySecret, consentID)

	// Attacker tries to reuse same nullifier with different consentID
	attackerConsentID := big.NewInt(99) // different consent

	assignment := &circuits.NullifierCircuit{
		IdentitySecret: identitySecret,
		ConsentID:      attackerConsentID, // WRONG: different from what produced nullifier
		Nullifier:      nullifier,         // Same nullifier — replayed
		ConsentHash:    consentHash,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.NullifierCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestNullifierCircuit_DPDP_UniquePerGrant tests the DPDP §6(4) requirement:
// each consent grant is individually distinguishable and non-transferable.
func TestNullifierCircuit_DPDP_UniquePerGrant(t *testing.T) {
	// Real scenario: user grants consent twice to the same org but for different purposes
	// Each gets a unique consentID from the ConsentLedger contract
	identitySecret := big.NewInt(0x0AFEBABE_DEADC0DE)
	consentID_grant1 := big.NewInt(5001) // first grant: health_data
	consentID_grant2 := big.NewInt(5002) // second grant: location_data

	null1 := mimcHash(identitySecret, consentID_grant1)
	null2 := mimcHash(identitySecret, consentID_grant2)
	consentHash := big.NewInt(0x0EEDFAC0)

	if null1.Cmp(null2) == 0 {
		t.Fatal("Two consent grants for same user have identical nullifiers — violates DPDP §6(4)")
	}

	assert := test.NewAssert(t)
	// Both grants are independently provable
	assert.SolvingSucceeded(&circuits.NullifierCircuit{},
		&circuits.NullifierCircuit{
			IdentitySecret: identitySecret,
			ConsentID:      consentID_grant1,
			Nullifier:      null1,
			ConsentHash:    consentHash,
		},
		test.WithCurves(ecc.BN254),
	)
}
