// Package circuits implements gnark ZK circuits for the ConsentLedger system.
//
// Three circuits are defined:
//   - AgeRangeCircuit:          Proves 18 ≤ secret_age ≤ 120 without revealing age.
//   - ConsentCommitmentCircuit: Proves knowledge of (data_type, purpose, salt) that hashes
//     to an on-chain commitment — consent metadata stays private.
//   - NullifierCircuit:         Proves SHA256(identity_secret || consent_id) = nullifier
//     for anti-replay protection — no competitor has this.
//
// All circuits use Groth16 over BN254 (same as TrustAnchor, but with additional
// commitment-binding that prevents proof replay attacks).
package circuits
