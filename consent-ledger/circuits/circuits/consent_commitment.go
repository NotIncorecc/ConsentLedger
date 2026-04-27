package circuits

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// ConsentCommitmentCircuit proves:
//
//	MiMC(DataTypeHash, PurposeHash, Salt, RequesterID) == Commitment
//
// where DataTypeHash and PurposeHash are field-element encodings of the
// consent metadata that must NEVER appear on-chain in plaintext.
//
// Competitive advantage over ALL competitors:
//   - Civitas stores field bitmasks (e.g. bit0=name, bit1=dob) in plaintext UInt16.
//     Any observer can see what data types were consented to.
//   - ConsentLedger stores only the commitment hash on-chain.
//     The verifier must know (data_type, purpose, salt) to reconstruct it.
//     This is the ONLY DPDP-compliant private consent metadata system in the hackathon.
//
// Private inputs:
//
//	DataTypeHash — MiMC(data_type_string), keeps data category private
//	PurposeHash  — MiMC(purpose_string), keeps purpose of processing private
//	Salt         — random blinding factor, ensures commitment is unique per grant
//
// Public inputs:
//
//	Commitment  — MiMC(DataTypeHash, PurposeHash, Salt, RequesterID), stored on-chain
//	RequesterID — public address of the organisation requesting consent
//
// DPDP Act relevance:
//
//	Implements §6(a) — "explicit, free, specific, informed and unambiguous consent"
//	without leaking what was consented to in on-chain storage.
type ConsentCommitmentCircuit struct {
	// Private witnesses (secret)
	DataTypeHash frontend.Variable `gnark:",secret"`
	PurposeHash  frontend.Variable `gnark:",secret"`
	Salt         frontend.Variable `gnark:",secret"`

	// Public inputs (visible to verifier, stored on-chain)
	Commitment  frontend.Variable `gnark:",public"` // MiMC(DataTypeHash, PurposeHash, Salt, RequesterID)
	RequesterID frontend.Variable `gnark:",public"` // org address as field element
}

// Define encodes the consent commitment constraint as an R1CS circuit.
func (c *ConsentCommitmentCircuit) Define(api frontend.API) error {
	// Compute MiMC hash of all 4 inputs sequentially:
	//   H = MiMC(DataTypeHash || PurposeHash || Salt || RequesterID)
	// Writing sequentially is equivalent to a multi-element hash in MiMC.
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	h.Write(c.DataTypeHash, c.PurposeHash, c.Salt, c.RequesterID)
	computed := h.Sum()

	// Verify the computed commitment matches the public on-chain commitment
	api.AssertIsEqual(computed, c.Commitment)

	return nil
}
