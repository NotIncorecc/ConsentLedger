from typing import Literal

from algopy import (
    ARC4Contract,
    Asset,
    BoxMap,
    Bytes,
    Global,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
)
from algopy.arc4 import abimethod


class ConsentRecord(arc4.Struct):
    owner: arc4.Address
    requester: arc4.Address
    # Phase 2: data_type/purpose replaced with ZK commitment hash (no plaintext on-chain)
    commitment: arc4.StaticArray[arc4.UInt8, Literal[32]]
    # nullifier = SHA256(identity_secret || consent_id) — prevents replay attacks
    nullifier: arc4.StaticArray[arc4.UInt8, Literal[32]]
    expiry: arc4.UInt64
    asset_id: arc4.UInt64
    # DPDP Act section: 6=§6 Standard, 9=§9 Children, 11=§11 Grievance, 16=§16 DPB Audit
    dpdp_section: arc4.UInt8


class ConsentLedger(ARC4Contract):
    """
    ConsentLedger - Decentralized ZK consent management on Algorand.

    Phase 2: data_type/purpose replaced with a Poseidon commitment hash.
    A nullifier prevents replay attacks. DPDP Act section recorded on-chain.
    Consent is minted as an ASA; revoking freezes it on-chain.
    """

    def __init__(self) -> None:
        # BoxMap keyed by owner(32)||requester(32) = exactly 64 bytes (AVM max).
        self.consents = BoxMap(Bytes, ConsentRecord, key_prefix=b"")
        # Nullifier registry — prefix(5) + nullifier(32) = 37 bytes total key.
        self.nullifiers = BoxMap(Bytes, arc4.Bool, key_prefix=b"null_")

    @abimethod()
    def grant_consent(
        self,
        requester: arc4.Address,
        commitment: arc4.StaticArray[arc4.UInt8, Literal[32]],
        nullifier: arc4.StaticArray[arc4.UInt8, Literal[32]],
        expiry: arc4.UInt64,
        dpdp_section: arc4.UInt8,
    ) -> arc4.UInt64:
        """
        Mint a consent ASA and store the ZK-committed record in box storage.

        commitment = Poseidon(data_type_hash, purpose_hash, salt) — data never
        touches the chain in plaintext.
        nullifier = SHA256(identity_secret || consent_id) — anti-replay.

        Returns the newly created asset ID.
        """
        # Anti-replay: nullifier must not already exist on-chain
        null_key = nullifier.bytes
        assert null_key not in self.nullifiers, "Nullifier already used (replay attack)"
        self.nullifiers[null_key] = arc4.Bool(True)

        # Mint 1 consent token (NFT-style, indivisible)
        mint_result = itxn.AssetConfig(
            total=1,
            decimals=0,
            unit_name=b"CONSENT",
            asset_name=b"ConsentToken",
            note=b"ConsentLedger|zk_committed",
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.current_application_address,
            clawback=Global.current_application_address,
            default_frozen=False,
            fee=0,
        ).submit()

        new_asset_id = mint_result.created_asset.id

        # Store ZK-committed consent record keyed by sender||requester (64 bytes)
        record = ConsentRecord(
            owner=arc4.Address(Txn.sender),
            requester=requester,
            commitment=commitment.copy(),
            nullifier=nullifier.copy(),
            expiry=expiry,
            asset_id=arc4.UInt64(new_asset_id),
            dpdp_section=dpdp_section,
        )
        box_key = Txn.sender.bytes + requester.bytes
        self.consents[box_key] = record.copy()

        return arc4.UInt64(new_asset_id)

    @abimethod()
    def revoke_consent(self, requester: arc4.Address) -> None:
        """
        Freeze the consent ASA to represent on-chain revocation.
        Only the original owner of the consent may call this.
        """
        box_key = Txn.sender.bytes + requester.bytes

        record = self.consents[box_key].copy()
        assert record.owner == arc4.Address(Txn.sender), "Only the owner can revoke consent"

        native_asset_id = record.asset_id.native

        itxn.AssetFreeze(
            freeze_asset=Asset(native_asset_id),
            freeze_account=Global.current_application_address,
            frozen=True,
            fee=0,
        ).submit()

    @abimethod(readonly=True)
    def is_consent_valid(
        self,
        owner: arc4.Address,
        requester: arc4.Address,
    ) -> arc4.Bool:
        """
        Read-only verifier: returns True if consent is active and not expired.
        Checks: record exists, expiry not passed, ASA not frozen.
        """
        box_key = owner.bytes + requester.bytes

        if box_key not in self.consents:
            return arc4.Bool(False)

        record = self.consents[box_key].copy()

        if record.expiry.native != 0 and record.expiry.native < Global.latest_timestamp:
            return arc4.Bool(False)

        native_asset_id = record.asset_id.native

        asset = Asset(native_asset_id)
        is_frozen, _exists = op.AssetHoldingGet.asset_frozen(
            Global.current_application_address, asset
        )
        if is_frozen:
            return arc4.Bool(False)

        return arc4.Bool(True)

    @abimethod(readonly=True)
    def get_consent_record(
        self,
        owner: arc4.Address,
        requester: arc4.Address,
    ) -> ConsentRecord:
        """
        Read-only: returns the full consent record.
        commitment is a hash — no plaintext data is ever stored or returned.
        """
        box_key = owner.bytes + requester.bytes
        assert box_key in self.consents, "No consent record found"
        return self.consents[box_key].copy()
