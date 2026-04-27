// ─── ConsentLedger Frontend Config ───────────────────────────────────────────
// Update app IDs and addresses after deploying each contract.
// Run: algokit project deploy localnet  →  note the printed app_id & app_address

export const CONFIG = {
  // ConsentLedger contract
  APP_ID: BigInt(import.meta.env.VITE_APP_ID ?? '0'),
  APP_ADDRESS: import.meta.env.VITE_APP_ADDRESS ?? '',

  // ZKVerifierContract
  ZK_VERIFIER_APP_ID: BigInt(import.meta.env.VITE_ZK_VERIFIER_APP_ID ?? '0'),

  // OrgRegistryContract
  ORG_REGISTRY_APP_ID: BigInt(import.meta.env.VITE_ORG_REGISTRY_APP_ID ?? '0'),
  ORG_REGISTRY_APP_ADDRESS: import.meta.env.VITE_ORG_REGISTRY_APP_ADDRESS ?? '',

  // FastAPI backend
  BACKEND_URL: import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000',

  // DigiLocker OAuth redirect (must match backend allowed origins)
  DIGILOCKER_REDIRECT_URI: import.meta.env.VITE_DIGILOCKER_REDIRECT_URI ?? 'http://localhost:5173/auth/callback',
} as const
