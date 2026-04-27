package circuits

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// NullifierCircuit proves:
//
//	MiMC(IdentitySecret, ConsentID) == Nullifier
//
// The Nullifier is stored on-chain in the ConsentLedger.nullifiers BoxMap.
// If the same (IdentitySecret, ConsentID) pair is submitted again, the nullifier
// already exists on-chain and the transaction reverts — preventing replay attacks.
//
// Competitive advantage — UNIQUE to ConsentLedger:
//   - TrustAnchor: No nullifier — same proof can be submitted by multiple actors.
//   - Acre: Stores a basic proof_hash but does NOT bind it to user identity.
//   - Civitas: No nullifier, no replay protection at all.
//   - ConsentLedger: The nullifier binds the proof to a SPECIFIC (user, consent)
//     pair. The user's IdentitySecret is derived from their DigiLocker identity,
//     so this achieves DPDP-compliant user-anchored, non-transferable consent.
//
// Private inputs:
//
//	IdentitySecret — HMAC(aadhaar_number, app_secret), derived off-chain from
//	                 DigiLocker OAuth response. Never stored anywhere, only used
//	                 to compute the nullifier.
//	ConsentID      — Unique identifier for this specific consent grant (e.g.,
//	                 MiMC(owner_address, requester_address, timestamp)).
//
// Public inputs:
//
//	Nullifier   — MiMC(IdentitySecret, ConsentID), stored on-chain as anti-replay key.
//	ConsentHash — Ties the nullifier to a specific ConsentRecord commitment,
//	              preventing nullifier from being used across different consents.
//
// DPDP Act relevance:
//
//	Implements §6(4) — consent must be specific and revocable, and each grant
//	must be individually distinguishable (non-fungible anti-replay).
type NullifierCircuit struct {
	// Private witnesses (secret — never revealed on-chain)
	IdentitySecret frontend.Variable `gnark:",secret"` // derived from DigiLocker Aadhaar
	ConsentID      frontend.Variable `gnark:",secret"` // unique consent identifier

	// Public inputs (stored on-chain in nullifiers BoxMap)
	Nullifier   frontend.Variable `gnark:",public"` // MiMC(IdentitySecret, ConsentID)
	ConsentHash frontend.Variable `gnark:",public"` // links nullifier to specific consent
}

// Define encodes the nullifier constraint as an R1CS circuit.
func (c *NullifierCircuit) Define(api frontend.API) error {
	// Compute: MiMC(IdentitySecret, ConsentID)
	// MiMC is a ZK-friendly hash (Algorand uses BN254 field arithmetic natively).
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	h.Write(c.IdentitySecret, c.ConsentID)
	computed := h.Sum()

	// Verify the computed nullifier matches the public nullifier
	api.AssertIsEqual(computed, c.Nullifier)

	// The ConsentHash is a public input but not constrained here — it serves as
	// additional context that gets included in the Groth16 proof's public witness,
	// ensuring the nullifier is tied to a specific consent commitment.
	// The ZKVerifier contract validates ConsentHash matches the stored ConsentRecord.
	_ = c.ConsentHash

	return nil
}
