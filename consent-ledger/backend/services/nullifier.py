"""
services/nullifier.py — Off-chain nullifier registry.

The primary nullifier store is the on-chain BoxMap in ConsentLedger. This
service provides fast pre-flight checks before constructing transactions,
avoiding wasted gas on guaranteed-to-fail submissions.

State is kept in memory (suitable for a single backend instance). Restart
resets the cache; the on-chain store remains the source of truth.
"""

from __future__ import annotations

import logging
from threading import Lock

logger = logging.getLogger(__name__)


class NullifierStore:
    """Thread-safe in-memory nullifier registry."""

    def __init__(self) -> None:
        self._used: set[str] = set()
        self._lock = Lock()

    def check(self, nullifier_hex: str) -> bool:
        """Return True if the nullifier has been used (replay detected)."""
        with self._lock:
            return nullifier_hex.lower() in self._used

    def mark_used(self, nullifier_hex: str) -> None:
        """Record a nullifier as used. Called after successful on-chain grant_consent."""
        with self._lock:
            self._used.add(nullifier_hex.lower())
            logger.debug("Nullifier marked used: %s", nullifier_hex[:16] + "…")

    def size(self) -> int:
        with self._lock:
            return len(self._used)
