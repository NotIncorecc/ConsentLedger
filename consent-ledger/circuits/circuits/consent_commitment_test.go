package circuits_test

import (
	"math/big"
	"testing"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend"
	"github.com/consensys/gnark/test"

	"consent-ledger/circuits/circuits"
)

// hashString converts a string to a big.Int field element by hashing it with MiMC.
// Used to convert data_type and purpose strings to circuit-compatible values.
func hashString(s string) *big.Int {
	return mimcHash(new(big.Int).SetBytes([]byte(s)))
}

// TestConsentCommitmentCircuit_Valid tests that valid consent metadata produces
// a correct commitment that satisfies the circuit.
func TestConsentCommitmentCircuit_Valid(t *testing.T) {
	// Simulate: user consents to sharing "health_data" for "insurance_claim"
	dataTypeHash := hashString("health_data")
	purposeHash := hashString("insurance_claim")
	salt := big.NewInt(246813579)
	requesterID := hashString("0xOrgWalletAddress123")

	// Compute the on-chain commitment
	commitment := mimcHash(dataTypeHash, purposeHash, salt, requesterID)

	assignment := &circuits.ConsentCommitmentCircuit{
		DataTypeHash: dataTypeHash,
		PurposeHash:  purposeHash,
		Salt:         salt,
		Commitment:   commitment,
		RequesterID:  requesterID,
	}

	assert := test.NewAssert(t)
	assert.ProverSucceeded(
		&circuits.ConsentCommitmentCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestConsentCommitmentCircuit_DifferentDataType tests that a different data type
// changes the commitment — proves specificity of consent.
func TestConsentCommitmentCircuit_DifferentDataType(t *testing.T) {
	// Original consent: health_data
	dataTypeHash := hashString("health_data")
	purposeHash := hashString("insurance_claim")
	salt := big.NewInt(111222333)
	requesterID := hashString("OrgB_wallet")

	commitment := mimcHash(dataTypeHash, purposeHash, salt, requesterID)

	// Try to satisfy with "financial_data" instead — should FAIL
	wrongDataTypeHash := hashString("financial_data")
	assignment := &circuits.ConsentCommitmentCircuit{
		DataTypeHash: wrongDataTypeHash, // WRONG
		PurposeHash:  purposeHash,
		Salt:         salt,
		Commitment:   commitment, // built from health_data
		RequesterID:  requesterID,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.ConsentCommitmentCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestConsentCommitmentCircuit_WrongRequester tests that swapping the requester
// organisation invalidates the commitment — prevents consent transfer between orgs.
func TestConsentCommitmentCircuit_WrongRequester(t *testing.T) {
	dataTypeHash := hashString("location_data")
	purposeHash := hashString("service_delivery")
	salt := big.NewInt(999888777)
	requesterID := hashString("OrgA_wallet")

	commitment := mimcHash(dataTypeHash, purposeHash, salt, requesterID)

	// Try to use consent for a different org — should FAIL
	wrongRequesterID := hashString("OrgB_wallet")
	assignment := &circuits.ConsentCommitmentCircuit{
		DataTypeHash: dataTypeHash,
		PurposeHash:  purposeHash,
		Salt:         salt,
		Commitment:   commitment,       // built for OrgA
		RequesterID:  wrongRequesterID, // WRONG — OrgB
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.ConsentCommitmentCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestConsentCommitmentCircuit_SaltUniqueness tests that two identical (data_type, purpose)
// with different salts produce different commitments — ensures consent uniqueness per grant.
func TestConsentCommitmentCircuit_SaltUniqueness(t *testing.T) {
	dataTypeHash := hashString("aadhaar")
	purposeHash := hashString("kyc_verification")
	requesterID := hashString("BankC_wallet")

	salt1 := big.NewInt(11111111)
	salt2 := big.NewInt(22222222)

	commitment1 := mimcHash(dataTypeHash, purposeHash, salt1, requesterID)
	commitment2 := mimcHash(dataTypeHash, purposeHash, salt2, requesterID)

	if commitment1.Cmp(commitment2) == 0 {
		t.Fatal("Two different salts produced the same commitment — salt is not effective")
	}

	// Both witnesses should succeed independently
	assert := test.NewAssert(t)
	assert.SolvingSucceeded(
		&circuits.ConsentCommitmentCircuit{},
		&circuits.ConsentCommitmentCircuit{
			DataTypeHash: dataTypeHash,
			PurposeHash:  purposeHash,
			Salt:         salt1,
			Commitment:   commitment1,
			RequesterID:  requesterID,
		},
		test.WithCurves(ecc.BN254),
	)
	assert.SolvingSucceeded(
		&circuits.ConsentCommitmentCircuit{},
		&circuits.ConsentCommitmentCircuit{
			DataTypeHash: dataTypeHash,
			PurposeHash:  purposeHash,
			Salt:         salt2,
			Commitment:   commitment2,
			RequesterID:  requesterID,
		},
		test.WithCurves(ecc.BN254),
	)
}

// TestConsentCommitmentCircuit_DPDP_HealthData tests a real DPDP §6 consent scenario:
// a health app requests access to medical history for treatment purposes.
func TestConsentCommitmentCircuit_DPDP_HealthData(t *testing.T) {
	// DPDP §6: Explicit, specific, informed consent
	dataTypeHash := hashString("medical_history")
	purposeHash := hashString("treatment_and_diagnosis")
	salt := big.NewInt(314159265)
	requesterID := hashString("Apollo_Hospitals_algo_address")

	commitment := mimcHash(dataTypeHash, purposeHash, salt, requesterID)

	assignment := &circuits.ConsentCommitmentCircuit{
		DataTypeHash: dataTypeHash,
		PurposeHash:  purposeHash,
		Salt:         salt,
		Commitment:   commitment,
		RequesterID:  requesterID,
	}

	assert := test.NewAssert(t)
	assert.SolvingSucceeded(
		&circuits.ConsentCommitmentCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
	)
}
