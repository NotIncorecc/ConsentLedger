/**
 * Decode a Phase-2 ARC-4 ConsentRecord from box storage.
 *
 * Layout (all static — no offset pointers):
 *   0..31    owner        arc4.Address (32 bytes)
 *  32..63    requester    arc4.Address (32 bytes)
 *  64..95    commitment   uint8[32]    — Poseidon(data_type_hash, purpose_hash, salt)
 *  96..127   nullifier    uint8[32]    — SHA256(identity_secret || consent_id)
 * 128..135   expiry       uint64       — Unix timestamp, 0 = no expiry
 * 136..143   asset_id     uint64
 *    144     dpdp_section uint8        — 6=§6, 9=§9, 11=§11, 16=§16
 * Total: 145 bytes
 */
export interface ConsentRecord {
  owner: string        // base32 Algorand address
  requester: string
  commitment: string   // hex string (32 bytes)
  nullifier: string    // hex string (32 bytes)
  expiry: bigint       // 0 = no expiry; otherwise Unix timestamp
  assetId: bigint
  dpdpSection: number  // 6 | 9 | 11 | 16
}

import algosdk from 'algosdk'

export function decodeConsentRecord(data: Uint8Array): ConsentRecord {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)

  const ownerBytes     = data.slice(0, 32)
  const reqBytes       = data.slice(32, 64)
  const commitment     = data.slice(64, 96)
  const nullifier      = data.slice(96, 128)
  const expiry         = view.getBigUint64(128, false)
  const assetId        = view.getBigUint64(136, false)
  const dpdpSection    = data[144] ?? 6

  const toHex = (bytes: Uint8Array) => Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')

  return {
    owner:        algosdk.encodeAddress(ownerBytes),
    requester:    algosdk.encodeAddress(reqBytes),
    commitment:   toHex(commitment),
    nullifier:    toHex(nullifier),
    expiry,
    assetId,
    dpdpSection,
  }
}

/** Short hex of a commitment (first 8 chars + "...") */
export function shortCommitment(hex: string): string {
  return hex.slice(0, 8) + '...'
}

/**
 * Build the box name for a consent record: owner_bytes(32) + requester_bytes(32) = 64 bytes.
 * 64 bytes is the AVM hard limit for box names.
 */
export function consentBoxName(ownerAddress: string, requesterAddress: string): Uint8Array {
  const ownerBytes = algosdk.decodeAddress(ownerAddress).publicKey      // 32 bytes
  const requesterBytes = algosdk.decodeAddress(requesterAddress).publicKey  // 32 bytes
  return new Uint8Array([...ownerBytes, ...requesterBytes])
}

/**
 * Parse a 64-byte box name: owner_bytes(32) + requester_bytes(32).
 * Returns null if the name is not exactly 64 bytes.
 */
export function parseConsentBoxName(name: Uint8Array): { owner: string; requester: string } | null {
  if (name.length !== 64) return null
  const ownerBytes = name.slice(0, 32)
  const requesterBytes = name.slice(32, 64)
  return {
    owner: algosdk.encodeAddress(ownerBytes),
    requester: algosdk.encodeAddress(requesterBytes),
  }
}

/**
 * Format a Unix timestamp (seconds) as a human-readable date, or "No expiry" if 0.
 */
export function formatExpiry(ts: bigint): string {
  if (ts === 0n) return 'No expiry'
  return new Date(Number(ts) * 1000).toLocaleDateString()
}

/**
 * Shorten an Algorand address for display.
 */
export function shortAddr(addr: string): string {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}
