package circuits

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
	"github.com/consensys/gnark/std/rangecheck"
)

// AgeRangeCircuit proves:
//
//	18 ≤ secret_age ≤ 120
//
// without revealing the actual age value.
//
// Competitive advantage over TrustAnchor's `greater_than` circuit:
//   - TrustAnchor proves income > threshold but has NO commitment binding.
//     The same proof can be replayed for any user by any verifier.
//   - This circuit binds the proof to commitment = MiMC(SecretAge, Salt).
//     The commitment is stored on-chain in the ConsentRecord.
//     Proof is only valid for the specific user who knows the pre-image.
//
// Private inputs:
//
//	SecretAge — the actual age (never revealed)
//	Salt      — random blinding factor (never revealed)
//
// Public inputs:
//
//	Commitment — MiMC(SecretAge, Salt), must match on-chain ConsentRecord.commitment
//
// DPDP Act relevance:
//
//	Used for §9 (Children's Data) consent — proves guardian is 18+ without storing DOB.
type AgeRangeCircuit struct {
	// Private witnesses (secret)
	SecretAge frontend.Variable `gnark:",secret"`
	Salt      frontend.Variable `gnark:",secret"`

	// Public inputs (visible to verifier)
	Commitment frontend.Variable `gnark:",public"` // MiMC(SecretAge, Salt)
}

const (
	// AgeMin is the minimum valid age for consent (DPDP Act requirement)
	AgeMin = 18
	// AgeMax is the maximum valid age (reasonable upper bound for range proof)
	AgeMax = 120
	// AgeMaxDiff = AgeMax - AgeMin = 102, fits in 7 bits (2^7 = 128 > 102)
	AgeMaxDiff = AgeMax - AgeMin
	// AgeRangeBits is the number of bits needed to represent AgeMaxDiff
	AgeRangeBits = 7
)

// Define encodes the age range constraint as an R1CS circuit.
func (c *AgeRangeCircuit) Define(api frontend.API) error {
	rc := rangecheck.New(api)

	// Constraint 1: SecretAge - AgeMin ≥ 0 and < 2^AgeRangeBits
	// This proves SecretAge ≥ AgeMin (18)
	diff1 := api.Sub(c.SecretAge, AgeMin)
	rc.Check(diff1, AgeRangeBits) // 0 ≤ diff1 < 128, combined with diff2 ≤ 102

	// Constraint 2: AgeMax - SecretAge ≥ 0 and < 2^AgeRangeBits
	// This proves SecretAge ≤ AgeMax (120)
	diff2 := api.Sub(AgeMax, c.SecretAge)
	rc.Check(diff2, AgeRangeBits) // 0 ≤ diff2 < 128

	// Constraint 3: Verify commitment = MiMC(SecretAge, Salt)
	// This binds the proof to the specific user — prevents replay attacks.
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	h.Write(c.SecretAge, c.Salt)
	computed := h.Sum()
	api.AssertIsEqual(computed, c.Commitment)

	return nil
}
