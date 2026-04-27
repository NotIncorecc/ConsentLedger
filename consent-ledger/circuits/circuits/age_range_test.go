package circuits_test

import (
	"math/big"
	"testing"

	"github.com/consensys/gnark-crypto/ecc"
	bls12381_mimc "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/consensys/gnark/backend"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/test"

	"consent-ledger/circuits/circuits"
)

// mimcHash computes MiMC(inputs...) off-circuit using gnark-crypto's native
// BN254 field MiMC implementation. Used to derive expected commitments for tests.
func mimcHash(inputs ...*big.Int) *big.Int {
	h := bls12381_mimc.NewMiMC()
	for _, v := range inputs {
		// Pad to 32 bytes (BN254 field element size)
		b := make([]byte, 32)
		v.FillBytes(b)
		h.Write(b)
	}
	result := h.Sum(nil)
	var out big.Int
	out.SetBytes(result)
	return &out
}

// TestAgeRangeCircuit_ValidAge tests that a valid age (≥18, ≤120) with a correct
// commitment satisfies the circuit.
func TestAgeRangeCircuit_ValidAge(t *testing.T) {
	secretAge := big.NewInt(25)
	salt := big.NewInt(123456789)
	commitment := mimcHash(secretAge, salt)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.ProverSucceeded(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_MinimumValidAge tests that age=18 (the exact minimum) satisfies.
func TestAgeRangeCircuit_MinimumValidAge(t *testing.T) {
	secretAge := big.NewInt(18)
	salt := big.NewInt(987654321)
	commitment := mimcHash(secretAge, salt)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.ProverSucceeded(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_MaximumValidAge tests that age=120 (the exact maximum) satisfies.
func TestAgeRangeCircuit_MaximumValidAge(t *testing.T) {
	secretAge := big.NewInt(120)
	salt := big.NewInt(111222333)
	commitment := mimcHash(secretAge, salt)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.ProverSucceeded(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_UnderageMinor tests that age=17 (minor) FAILS the circuit.
// This is the key DPDP §9 protection — minors cannot grant independent consent.
func TestAgeRangeCircuit_UnderageMinor(t *testing.T) {
	secretAge := big.NewInt(17)
	salt := big.NewInt(555666777)
	commitment := mimcHash(secretAge, salt)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_WrongCommitment tests that a tampered commitment FAILS.
// This verifies the anti-replay binding — you cannot submit someone else's age proof.
func TestAgeRangeCircuit_WrongCommitment(t *testing.T) {
	secretAge := big.NewInt(30)
	salt := big.NewInt(444555666)
	// Tampered commitment — does NOT match MiMC(30, salt)
	tamperedCommitment := big.NewInt(9999999)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: tamperedCommitment,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_AgeZeroFails tests that age=0 is rejected.
func TestAgeRangeCircuit_AgeZeroFails(t *testing.T) {
	secretAge := big.NewInt(0)
	salt := big.NewInt(777888999)
	commitment := mimcHash(secretAge, salt)

	assignment := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.ProverFailed(
		&circuits.AgeRangeCircuit{},
		assignment,
		test.WithCurves(ecc.BN254),
		test.WithBackends(backend.GROTH16),
	)
}

// TestAgeRangeCircuit_SatisfyingWitness tests circuit satisfaction directly
// without full Groth16 proof generation (faster for development).
func TestAgeRangeCircuit_SatisfyingWitness(t *testing.T) {
	secretAge := big.NewInt(35)
	salt := big.NewInt(135792468)
	commitment := mimcHash(secretAge, salt)

	witness := &circuits.AgeRangeCircuit{
		SecretAge:  secretAge,
		Salt:       salt,
		Commitment: commitment,
	}

	assert := test.NewAssert(t)
	assert.SolvingSucceeded(&circuits.AgeRangeCircuit{}, witness, test.WithCurves(ecc.BN254))
}

// TestAgeRangeCircuit_Compile verifies the circuit compiles without errors.
func TestAgeRangeCircuit_Compile(t *testing.T) {
	assert := test.NewAssert(t)
	var c circuits.AgeRangeCircuit
	assert.SolvingSucceeded(&c,
		&circuits.AgeRangeCircuit{
			SecretAge:  frontend.Variable(25),
			Salt:       frontend.Variable(1),
			Commitment: mimcHash(big.NewInt(25), big.NewInt(1)),
		},
		test.WithCurves(ecc.BN254),
	)
}
