"""
services/digilocker.py — DigiLocker OAuth2 integration.

DigiLocker is India's official digital document wallet. The OAuth2 flow here
retrieves an Aadhaar-verified date-of-birth and UID number that are used
exclusively to derive ZK witness inputs. No raw Aadhaar data is ever stored.

MOCK MODE: When DIGILOCKER_CLIENT_ID is empty the service returns synthetic
data so the full ZK proof flow can be exercised on a dev machine without real
DigiLocker credentials.

Reference: https://partners.digitallocker.gov.in/eaadhaar/
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import date
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ──────────────────────── DigiLocker OAuth constants ─────────────────────────

_AUTH_URL = "https://api.digitallocker.gov.in/public/oauth2/1/authorize"
_TOKEN_URL = "https://api.digitallocker.gov.in/public/oauth2/1/token"
_EAADHAAR_URL = "https://api.digitallocker.gov.in/public/oauth2/3/xml/eaadhaar"


class DigiLockerService:
    """Thin wrapper around the DigiLocker OAuth2 API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        app_secret: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.app_secret = app_secret
        self._mock_mode = not bool(client_id)

        if self._mock_mode:
            logger.warning(
                "DigiLockerService: DIGILOCKER_CLIENT_ID not set — running in mock mode. "
                "All identity data will be synthetic."
            )

    # ──────────────────────── Public API ──────────────────────────────────

    def get_auth_url(self, state: str) -> str:
        """
        Step 1 — Return the DigiLocker OAuth2 authorisation URL.

        The frontend redirects the user to this URL. DigiLocker authenticates
        the user and redirects back to `redirect_uri?code=<code>&state=<state>`.
        """
        if self._mock_mode:
            return f"/auth/digilocker/mock-callback?state={state}"

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "openid profile",
            "dl_flow": "signup",
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """
        Step 2 — Exchange auth code for an access token.

        Returns the token response dict (access_token, id_token, …).
        Raises httpx.HTTPStatusError on failure.
        """
        if self._mock_mode:
            return {"access_token": "mock_token", "id_token": "mock_id"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_identity_for_zk(self, access_token: str) -> dict:
        """
        Step 3 — Fetch eAadhaar XML and extract only what the ZK circuits need.

        Returns a dict with:
          - age (int) — computed from DOB, never the raw DOB
          - identity_secret (str) — HMAC(sha256(aadhaar_uid), app_secret) as hex
            This is a one-way derivation; raw UID is discarded after this function.

        SECURITY: Raw Aadhaar or DOB are NEVER returned, logged, or persisted.
        """
        if self._mock_mode:
            return self._mock_identity()

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _EAADHAAR_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                xml_text = resp.text

            age, identity_secret = self._parse_aadhaar_xml(xml_text)
        except Exception as exc:
            logger.error("DigiLocker eAadhaar fetch failed: %s", exc)
            raise

        return {
            "age": age,
            "identity_secret": identity_secret,
        }

    # ──────────────────────── Private helpers ─────────────────────────────

    def _parse_aadhaar_xml(self, xml_text: str) -> tuple[int, str]:
        """
        Parse eAadhaar XML for DOB and UID.

        eAadhaar XML contains a `dob` attribute (DD-MM-YYYY) and a `uid` attribute.
        We compute age and then immediately discard DOB and UID.
        """
        import xml.etree.ElementTree as ET  # stdlib — safe for untrusted XML via defusedxml

        try:
            import defusedxml.ElementTree as DET  # safe XML parser
            root = DET.fromstring(xml_text)
        except ImportError:
            # Fallback to stdlib — acceptable for this input since it comes from
            # a TLS-authenticated DigiLocker server, not user input.
            root = ET.fromstring(xml_text)

        # eAadhaar XML structure: <OfflinePaperlessKyc><UidData dob="DD-MM-YYYY" uid="XXXX">
        uid_data = root.find(".//UidData")
        if uid_data is None:
            raise ValueError("UidData element not found in eAadhaar XML")

        dob_str: str = uid_data.get("dob", "")
        uid_raw: str = uid_data.get("uid", "")

        day, month, year = (int(x) for x in dob_str.split("-"))
        today = date.today()
        age = (
            today.year
            - year
            - ((today.month, today.day) < (month, day))
        )

        # Derive a one-way identity secret: HMAC-SHA256(aadhaar_uid, app_secret)
        identity_secret = hmac.new(
            self.app_secret.encode(),
            uid_raw.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Immediately clear sensitive variables
        del uid_raw, dob_str

        return age, identity_secret

    def _mock_identity(self) -> dict:
        """Return synthetic identity data for development / testing."""
        return {
            "age": 28,  # a legal adult
            "identity_secret": hashlib.sha256(b"mock_identity_secret").hexdigest(),
        }
