"""
config.py — Centralised settings for the ConsentLedger backend.

All values default to the public testnet AlgoNode endpoints and the
deployed app IDs from Phase 2. Override via environment variables or a
.env file placed in the backend/ directory.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ──────────────────────── Algorand node ────────────────────────────────
    algod_server: str = "https://testnet-api.algonode.cloud"
    algod_port: int = 443
    algod_token: str = ""
    indexer_server: str = "https://testnet-idx.algonode.cloud"
    indexer_port: int = 443
    indexer_token: str = ""

    # ──────────────────────── Backend signer ───────────────────────────────
    # Deployer mnemonic: the account that deployed the contracts and is
    # authorised to call confirm_verification() on ZKVerifierContract.
    deployer_mnemonic: str = ""

    # ──────────────────────── Deployed app IDs (testnet Phase 2) ──────────
    consent_ledger_app_id: int = 759443293
    zk_verifier_app_id: int = 759443440
    org_registry_app_id: int = 759443291

    # ──────────────────────── DigiLocker OAuth ────────────────────────────
    digilocker_client_id: str = ""
    digilocker_client_secret: str = ""
    digilocker_redirect_uri: str = "http://localhost:8000/auth/digilocker/callback"

    # HMAC key used to derive identity_secret from Aadhaar number.
    # NEVER expose this value in logs or API responses.
    app_secret: str = "consent-ledger-dev-secret-change-in-production"

    # ──────────────────────── ZK prover ───────────────────────────────────
    # Absolute path to the compiled gnark prover binary.
    # When the binary is not present the service falls back to simulation mode.
    prover_binary: str = "../circuits/prover"
    prover_keys_dir: str = "../circuits/keys"

    # ──────────────────────── x402 payments ───────────────────────────────
    # Amount in microAlgo that a verifier must pay to call is_consent_valid.
    consent_fee_microalgo: int = 100_000  # 0.1 ALGO

    # ──────────────────────── CORS ────────────────────────────────────────
    cors_origins: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "https://consent-ledger.vercel.app",
    ]

    # ──────────────────────── JWT (session tokens) ────────────────────────
    jwt_secret: str = "consent-ledger-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


settings = Settings()
