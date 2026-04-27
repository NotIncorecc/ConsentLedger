// cmd/main.go — ConsentLedger ZK Circuit CLI
//
// Subcommands:
//
//	setup   — Compile circuit and run Groth16 trusted setup, saving proving/verifying keys.
//	prove   — Load proving key, create witness, generate Groth16 proof, output JSON.
//	verify  — Load verifying key, verify a proof JSON file.
//
// Usage:
//
//	go run cmd/main.go setup   --circuit age_range         --keys-dir keys/age_range/
//	go run cmd/main.go setup   --circuit consent_commitment --keys-dir keys/consent_commitment/
//	go run cmd/main.go setup   --circuit nullifier          --keys-dir keys/nullifier/
//
//	go run cmd/main.go prove   --circuit age_range \
//	                           --witness '{"secret_age":25,"salt":123456}' \
//	                           --keys-dir keys/age_range/ \
//	                           --out proof_age.json
//
//	go run cmd/main.go verify  --circuit age_range \
//	                           --proof proof_age.json \
//	                           --keys-dir keys/age_range/
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math/big"
	"os"
	"path/filepath"

	"github.com/consensys/gnark-crypto/ecc"
	bls12381_mimc "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"

	"consent-ledger/circuits/circuits"
)

// ProofOutput is the JSON format written to --out file and sent to the backend.
// The backend submits proof_hash to ZKVerifierContract.submit_proof().
type ProofOutput struct {
	Circuit      string            `json:"circuit"`
	Proof        string            `json:"proof"`         // base64-encoded groth16 proof bytes
	PublicInputs map[string]string `json:"public_inputs"` // hex-encoded field elements
	ProofHash    string            `json:"proof_hash"`    // SHA256(proof_bytes) for on-chain reference
}

// AgeWitness is the JSON input format for age_range circuit proving.
type AgeWitness struct {
	SecretAge int64 `json:"secret_age"`
	Salt      int64 `json:"salt"`
}

// ConsentCommitmentWitness is the JSON input for consent_commitment circuit proving.
type ConsentCommitmentWitness struct {
	DataType    string `json:"data_type"` // plain-text (never leaves this machine)
	Purpose     string `json:"purpose"`   // plain-text (never leaves this machine)
	Salt        int64  `json:"salt"`
	RequesterID string `json:"requester_id"` // org Algorand address (hex)
}

// NullifierWitness is the JSON input for nullifier circuit proving.
type NullifierWitness struct {
	IdentitySecret string `json:"identity_secret"` // hex-encoded HMAC(aadhaar, app_secret)
	ConsentID      int64  `json:"consent_id"`
	ConsentHash    string `json:"consent_hash"` // hex-encoded on-chain commitment
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}

	switch os.Args[1] {
	case "setup":
		runSetup(os.Args[2:])
	case "prove":
		runProve(os.Args[2:])
	case "verify":
		runVerify(os.Args[2:])
	default:
		fmt.Fprintf(os.Stderr, "Unknown subcommand: %s\n", os.Args[1])
		usage()
		os.Exit(1)
	}
}

func usage() {
	fmt.Println(`ConsentLedger ZK Circuit CLI

Subcommands:
  setup   --circuit <name> --keys-dir <dir>
  prove   --circuit <name> --witness <json> --keys-dir <dir> --out <file>
  verify  --circuit <name> --proof <file> --keys-dir <dir>

Circuit names: age_range, consent_commitment, nullifier`)
}

// ─── SETUP ───────────────────────────────────────────────────────────────────

func runSetup(args []string) {
	fs := flag.NewFlagSet("setup", flag.ExitOnError)
	circuitName := fs.String("circuit", "", "Circuit name (age_range|consent_commitment|nullifier)")
	keysDir := fs.String("keys-dir", "", "Directory to write proving and verifying keys")
	fs.Parse(args)

	if *circuitName == "" || *keysDir == "" {
		fmt.Fprintln(os.Stderr, "setup: --circuit and --keys-dir are required")
		os.Exit(1)
	}

	if err := os.MkdirAll(*keysDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create keys dir: %v\n", err)
		os.Exit(1)
	}

	circuit := buildCircuit(*circuitName)
	fmt.Printf("[setup] Compiling circuit: %s\n", *circuitName)

	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, circuit)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Circuit compile failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[setup] Running Groth16 trusted setup (BN254)...\n")
	pk, vk, err := groth16.Setup(ccs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Groth16 setup failed: %v\n", err)
		os.Exit(1)
	}

	// Save proving key
	pkPath := filepath.Join(*keysDir, "pk.groth16.key")
	pkFile, _ := os.Create(pkPath)
	defer pkFile.Close()
	_, err = pk.WriteTo(pkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write proving key: %v\n", err)
		os.Exit(1)
	}

	// Save verifying key
	vkPath := filepath.Join(*keysDir, "vk.groth16.key")
	vkFile, _ := os.Create(vkPath)
	defer vkFile.Close()
	_, err = vk.WriteTo(vkFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write verifying key: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[setup] Done.\n")
	fmt.Printf("  Proving key:   %s\n", pkPath)
	fmt.Printf("  Verifying key: %s\n", vkPath)
	fmt.Printf("  Constraints:   %d\n", ccs.GetNbConstraints())
}

// ─── PROVE ───────────────────────────────────────────────────────────────────

func runProve(args []string) {
	fs := flag.NewFlagSet("prove", flag.ExitOnError)
	circuitName := fs.String("circuit", "", "Circuit name")
	witnessJSON := fs.String("witness", "", "Witness JSON string (or @file to read from file)")
	keysDir := fs.String("keys-dir", "", "Directory with pk.groth16.key")
	outPath := fs.String("out", "proof.json", "Output file for proof JSON")
	fs.Parse(args)

	if *circuitName == "" || *witnessJSON == "" || *keysDir == "" {
		fmt.Fprintln(os.Stderr, "prove: --circuit, --witness, and --keys-dir are required")
		os.Exit(1)
	}

	// Support @filename for witness input
	witnessData := *witnessJSON
	if len(witnessData) > 0 && witnessData[0] == '@' {
		b, err := os.ReadFile(witnessData[1:])
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to read witness file: %v\n", err)
			os.Exit(1)
		}
		witnessData = string(b)
	}

	// Build the circuit assignment from the witness
	circuit, publicInputNames := buildAssignment(*circuitName, witnessData)

	// Re-compile the circuit to get the constraint system (same as setup step)
	baseCircuit := buildCircuit(*circuitName)
	fmt.Printf("[prove] Compiling circuit: %s\n", *circuitName)
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, baseCircuit)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Circuit compile failed: %v\n", err)
		os.Exit(1)
	}

	// Load proving key
	pkPath := filepath.Join(*keysDir, "pk.groth16.key")
	pkFile, err := os.Open(pkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open proving key: %v (run setup first)\n", err)
		os.Exit(1)
	}
	defer pkFile.Close()

	pk := groth16.NewProvingKey(ecc.BN254)
	if _, err := pk.ReadFrom(pkFile); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read proving key: %v\n", err)
		os.Exit(1)
	}

	// Create witness
	fmt.Printf("[prove] Creating witness for circuit: %s\n", *circuitName)
	w, err := frontend.NewWitness(circuit, ecc.BN254.ScalarField())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create witness: %v\n", err)
		os.Exit(1)
	}

	// Generate proof
	fmt.Printf("[prove] Generating Groth16 proof...\n")
	proof, err := groth16.Prove(ccs, pk, w)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Proof generation failed: %v\n", err)
		os.Exit(1)
	}

	// Serialize proof to bytes
	var proofBuf bytes.Buffer
	proof.WriteTo(&proofBuf)
	proofBytes := proofBuf.Bytes()

	// Compute proof hash (SHA256) for on-chain reference
	hash := sha256.Sum256(proofBytes)
	proofHash := hex.EncodeToString(hash[:])

	// Build output
	output := ProofOutput{
		Circuit:      *circuitName,
		Proof:        base64.StdEncoding.EncodeToString(proofBytes),
		PublicInputs: publicInputNames,
		ProofHash:    proofHash,
	}

	outBytes, _ := json.MarshalIndent(output, "", "  ")
	if err := os.WriteFile(*outPath, outBytes, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write proof: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[prove] Done.\n")
	fmt.Printf("  Proof file:  %s\n", *outPath)
	fmt.Printf("  Proof hash:  %s\n", proofHash)
	fmt.Printf("  (Submit proof_hash to ZKVerifierContract.submit_proof())\n")
}

// ─── VERIFY ───────────────────────────────────────────────────────────────────

func runVerify(args []string) {
	fs := flag.NewFlagSet("verify", flag.ExitOnError)
	circuitName := fs.String("circuit", "", "Circuit name")
	proofPath := fs.String("proof", "", "Path to proof JSON file")
	keysDir := fs.String("keys-dir", "", "Directory with vk.groth16.key")
	fs.Parse(args)

	if *circuitName == "" || *proofPath == "" || *keysDir == "" {
		fmt.Fprintln(os.Stderr, "verify: --circuit, --proof, and --keys-dir are required")
		os.Exit(1)
	}

	// Load verifying key
	vkPath := filepath.Join(*keysDir, "vk.groth16.key")
	vkFile, err := os.Open(vkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open verifying key: %v\n", err)
		os.Exit(1)
	}
	defer vkFile.Close()

	vk := groth16.NewVerifyingKey(ecc.BN254)
	if _, err := vk.ReadFrom(vkFile); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read verifying key: %v\n", err)
		os.Exit(1)
	}

	// Load proof
	proofData, err := os.ReadFile(*proofPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read proof file: %v\n", err)
		os.Exit(1)
	}

	var output ProofOutput
	if err := json.Unmarshal(proofData, &output); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to parse proof JSON: %v\n", err)
		os.Exit(1)
	}

	proofBytes, err := base64.StdEncoding.DecodeString(output.Proof)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to decode proof: %v\n", err)
		os.Exit(1)
	}

	// Verify proof hash integrity
	hash := sha256.Sum256(proofBytes)
	expectedHash := hex.EncodeToString(hash[:])
	if expectedHash != output.ProofHash {
		fmt.Fprintf(os.Stderr, "Proof hash mismatch! Proof may have been tampered.\n")
		os.Exit(1)
	}

	proof := groth16.NewProof(ecc.BN254)
	if _, err := proof.ReadFrom(bytes.NewReader(proofBytes)); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to deserialize proof: %v\n", err)
		os.Exit(1)
	}

	// Reconstruct public witness from public_inputs in JSON
	publicWitness := buildPublicWitness(*circuitName, output.PublicInputs)
	pw, err := frontend.NewWitness(publicWitness, ecc.BN254.ScalarField(), frontend.PublicOnly())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create public witness: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[verify] Verifying Groth16 proof for circuit: %s\n", *circuitName)
	if err := groth16.Verify(proof, vk, pw); err != nil {
		fmt.Printf("  INVALID — proof verification FAILED: %v\n", err)
		os.Exit(2)
	}

	fmt.Printf("  VALID — proof verified successfully ✓\n")
	fmt.Printf("  Circuit:    %s\n", output.Circuit)
	fmt.Printf("  ProofHash:  %s\n", output.ProofHash)
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

// buildCircuit returns an unassigned circuit for the given name.
func buildCircuit(name string) frontend.Circuit {
	switch name {
	case "age_range":
		return &circuits.AgeRangeCircuit{}
	case "consent_commitment":
		return &circuits.ConsentCommitmentCircuit{}
	case "nullifier":
		return &circuits.NullifierCircuit{}
	default:
		fmt.Fprintf(os.Stderr, "Unknown circuit: %s\n", name)
		os.Exit(1)
		return nil
	}
}

// buildAssignment creates a fully-assigned circuit from a witness JSON string.
// Returns the circuit and a map of public input names/values for the proof output.
func buildAssignment(circuitName, witnessJSON string) (frontend.Circuit, map[string]string) {
	switch circuitName {
	case "age_range":
		return buildAgeRangeAssignment(witnessJSON)
	case "consent_commitment":
		return buildConsentCommitmentAssignment(witnessJSON)
	case "nullifier":
		return buildNullifierAssignment(witnessJSON)
	default:
		fmt.Fprintf(os.Stderr, "Unknown circuit: %s\n", circuitName)
		os.Exit(1)
		return nil, nil
	}
}

func buildAgeRangeAssignment(witnessJSON string) (frontend.Circuit, map[string]string) {
	var w AgeWitness
	if err := json.Unmarshal([]byte(witnessJSON), &w); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to parse age_range witness: %v\n", err)
		os.Exit(1)
	}

	age := big.NewInt(w.SecretAge)
	salt := big.NewInt(w.Salt)
	commitment := mimcHashNative(age, salt)

	circuit := &circuits.AgeRangeCircuit{
		SecretAge:  age,
		Salt:       salt,
		Commitment: commitment,
	}

	publicInputs := map[string]string{
		"commitment": hex.EncodeToString(commitment.Bytes()),
	}

	fmt.Printf("[prove] Age range: %d ≤ %d ≤ %d\n", circuits.AgeMin, w.SecretAge, circuits.AgeMax)
	fmt.Printf("[prove] Commitment: 0x%s\n", publicInputs["commitment"])

	return circuit, publicInputs
}

func buildConsentCommitmentAssignment(witnessJSON string) (frontend.Circuit, map[string]string) {
	var w ConsentCommitmentWitness
	if err := json.Unmarshal([]byte(witnessJSON), &w); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to parse consent_commitment witness: %v\n", err)
		os.Exit(1)
	}

	dataTypeHash := mimcHashNative(new(big.Int).SetBytes([]byte(w.DataType)))
	purposeHash := mimcHashNative(new(big.Int).SetBytes([]byte(w.Purpose)))
	salt := big.NewInt(w.Salt)
	requesterBytes, _ := hex.DecodeString(w.RequesterID)
	requesterID := new(big.Int).SetBytes(requesterBytes)

	commitment := mimcHashNative(dataTypeHash, purposeHash, salt, requesterID)

	circuit := &circuits.ConsentCommitmentCircuit{
		DataTypeHash: dataTypeHash,
		PurposeHash:  purposeHash,
		Salt:         salt,
		Commitment:   commitment,
		RequesterID:  requesterID,
	}

	publicInputs := map[string]string{
		"commitment":   hex.EncodeToString(commitment.Bytes()),
		"requester_id": hex.EncodeToString(requesterID.Bytes()),
	}

	fmt.Printf("[prove] Consent commitment for requester: %s\n", w.RequesterID)
	fmt.Printf("[prove] Commitment: 0x%s\n", publicInputs["commitment"])

	return circuit, publicInputs
}

func buildNullifierAssignment(witnessJSON string) (frontend.Circuit, map[string]string) {
	var w NullifierWitness
	if err := json.Unmarshal([]byte(witnessJSON), &w); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to parse nullifier witness: %v\n", err)
		os.Exit(1)
	}

	secretBytes, _ := hex.DecodeString(w.IdentitySecret)
	identitySecret := new(big.Int).SetBytes(secretBytes)
	consentID := big.NewInt(w.ConsentID)
	consentHashBytes, _ := hex.DecodeString(w.ConsentHash)
	consentHash := new(big.Int).SetBytes(consentHashBytes)

	nullifier := mimcHashNative(identitySecret, consentID)

	circuit := &circuits.NullifierCircuit{
		IdentitySecret: identitySecret,
		ConsentID:      consentID,
		Nullifier:      nullifier,
		ConsentHash:    consentHash,
	}

	publicInputs := map[string]string{
		"nullifier":    hex.EncodeToString(nullifier.Bytes()),
		"consent_hash": hex.EncodeToString(consentHash.Bytes()),
	}

	fmt.Printf("[prove] Nullifier: 0x%s\n", publicInputs["nullifier"])

	return circuit, publicInputs
}

// buildPublicWitness reconstructs the public-only circuit from proof output public_inputs.
func buildPublicWitness(circuitName string, publicInputs map[string]string) frontend.Circuit {
	hexToBigInt := func(h string) *big.Int {
		b, _ := hex.DecodeString(h)
		return new(big.Int).SetBytes(b)
	}

	switch circuitName {
	case "age_range":
		return &circuits.AgeRangeCircuit{
			Commitment: hexToBigInt(publicInputs["commitment"]),
		}
	case "consent_commitment":
		return &circuits.ConsentCommitmentCircuit{
			Commitment:  hexToBigInt(publicInputs["commitment"]),
			RequesterID: hexToBigInt(publicInputs["requester_id"]),
		}
	case "nullifier":
		return &circuits.NullifierCircuit{
			Nullifier:   hexToBigInt(publicInputs["nullifier"]),
			ConsentHash: hexToBigInt(publicInputs["consent_hash"]),
		}
	default:
		fmt.Fprintf(os.Stderr, "Unknown circuit: %s\n", circuitName)
		os.Exit(1)
		return nil
	}
}

// mimcHashNative computes MiMC hash off-circuit using gnark-crypto BN254 MiMC.
// Matches the in-circuit computation in the circuit definitions.
func mimcHashNative(inputs ...*big.Int) *big.Int {
	h := bls12381_mimc.NewMiMC()
	for _, v := range inputs {
		b := make([]byte, 32)
		v.FillBytes(b)
		h.Write(b)
	}
	result := h.Sum(nil)
	return new(big.Int).SetBytes(result)
}
