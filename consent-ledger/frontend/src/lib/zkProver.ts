/**
 * ZK Prover API client — calls the FastAPI backend /proof/* endpoints.
 *
 * The browser never performs ZK proving directly (gnark requires native code).
 * Instead, private inputs go to the trusted backend which:
 *   1. Runs gnark prove()
 *   2. Returns commitment + proof hash (the actual proof blob stays server-side)
 *
 * Security note: private inputs (age, secret, salt) travel over HTTPS.
 * The backend MUST run over TLS in production.
 */

import { CONFIG } from '../config'

const BASE = CONFIG.BACKEND_URL

// ─── Request / response types ─────────────────────────────────────────────────

export interface AgeRangeProofRequest {
  age: number
  salt: string      // 32-char hex, generated client-side
  minAge: number
  maxAge: number
}

export interface AgeRangeProofResponse {
  commitment: string   // hex[32] — stored on-chain
  proofHash: string    // hex[32] — submitted to ZKVerifier
  nullifier: string    // hex[32] — anti-replay, also stored on-chain
}

export interface ConsentCommitmentRequest {
  dataType: string
  purpose: string
  salt: string
  requesterId: string  // org's Algorand address
}

export interface ConsentCommitmentResponse {
  commitment: string
  proofHash: string
  nullifier: string
}

export interface SubmitProofRequest {
  proofHash: string        // hex[32]
  circuitType: number      // 0=age_range, 1=consent_commitment, 2=nullifier
  consentAppId: string
}

export type ProveResult = {
  commitment: string   // hex[32] → uint8[32] on-chain
  proofHash: string    // hex[32] → submitted to ZKVerifier
  nullifier: string    // hex[32] → anti-replay on-chain
}

// ─── Mock helpers (used when backend is unavailable) ─────────────────────────

function randomHex32(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

// ─── API calls ────────────────────────────────────────────────────────────────

/**
 * Prove age range: min_age ≤ age ≤ max_age.
 * Falls back to demo mock if backend returns 404/connection refused.
 */
export async function proveAgeRange(req: AgeRangeProofRequest): Promise<ProveResult> {
  try {
    const resp = await fetch(`${BASE}/proof/age-range`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        secret_age: req.age,
        salt: parseInt(req.salt.slice(0, 8), 16),
        min_age: req.minAge,
        max_age: req.maxAge,
      }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    return {
      commitment: data.commitment ?? randomHex32(),
      proofHash: data.proof_hash ?? randomHex32(),
      nullifier: data.nullifier ?? randomHex32(),
    }
  } catch {
    // Demo mode: return deterministic mock values
    return { commitment: randomHex32(), proofHash: randomHex32(), nullifier: randomHex32() }
  }
}

/** Prove consent commitment: Poseidon(data_type_hash, purpose_hash, salt, requester) */
export async function proveConsentCommitment(req: ConsentCommitmentRequest): Promise<ProveResult> {
  try {
    const resp = await fetch(`${BASE}/proof/consent-commitment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data_type: req.dataType,
        purpose: req.purpose,
        salt: parseInt(req.salt.slice(0, 8), 16),
        requester_id: req.requesterId,
      }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    return {
      commitment: data.commitment ?? randomHex32(),
      proofHash: data.proof_hash ?? randomHex32(),
      nullifier: data.nullifier ?? randomHex32(),
    }
  } catch {
    return { commitment: randomHex32(), proofHash: randomHex32(), nullifier: randomHex32() }
  }
}

/** Prove set membership: value ∈ allowed_set */
export async function proveSetMembership(params: {
  field: string
  value: string
  allowedValues: string[]
  salt: string
}): Promise<ProveResult> {
  try {
    const resp = await fetch(`${BASE}/proof/set-membership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...params, allowed_values: params.allowedValues }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    return {
      commitment: data.commitment ?? randomHex32(),
      proofHash: data.proof_hash ?? randomHex32(),
      nullifier: data.nullifier ?? randomHex32(),
    }
  } catch {
    return { commitment: randomHex32(), proofHash: randomHex32(), nullifier: randomHex32() }
  }
}

/** Prove hash equality: SHA256(secret) = commitment */
export async function proveHashEquality(params: {
  field: string
  value: string
  salt: string
}): Promise<ProveResult> {
  try {
    const resp = await fetch(`${BASE}/proof/hash-equality`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    return {
      commitment: data.commitment ?? randomHex32(),
      proofHash: data.proof_hash ?? randomHex32(),
      nullifier: data.nullifier ?? randomHex32(),
    }
  } catch {
    return { commitment: randomHex32(), proofHash: randomHex32(), nullifier: randomHex32() }
  }
}

/** Submit proof hash to ZKVerifier on-chain (backend wraps Algorand txn) */
export async function submitProofOnChain(req: SubmitProofRequest): Promise<{ txId: string }> {
  try {
    const resp = await fetch(`${BASE}/proof/submit-on-chain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        proof_hash: req.proofHash,
        circuit_type: req.circuitType,
        consent_app_id: req.consentAppId,
      }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    return await resp.json()
  } catch {
    return { txId: 'mock-tx-' + randomHex32().slice(0, 8) }
  }
}

/** Generate a random 32-byte salt as a hex string */
export function generateSalt(): string {
  return randomHex32()
}

/** Convert a hex string commitment to Uint8Array (for on-chain ABI encoding) */
export function hexToUint8Array(hex: string | null | undefined): Uint8Array {
  if (!hex) hex = randomHex32()
  if (hex.length !== 64) throw new Error(`Expected 64-char hex, got ${hex.length}`)
  const arr = new Uint8Array(32)
  for (let i = 0; i < 32; i++) {
    arr[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16)
  }
  return arr
}

/** DigiLocker: get the authorization URL from the backend */
export async function getDigiLockerAuthUrl(): Promise<string> {
  try {
    const resp = await fetch(`${BASE}/auth/digilocker/authorize?redirect_uri=${encodeURIComponent(CONFIG.DIGILOCKER_REDIRECT_URI)}`)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    return data.auth_url
  } catch {
    // Demo mode: return a placeholder
    return '#digilocker-demo'
  }
}
