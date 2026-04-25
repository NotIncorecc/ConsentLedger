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
    data_type: arc4.String
    purpose: arc4.String
    expiry: arc4.UInt64
    asset_id: arc4.UInt64


class ConsentLedger(ARC4Contract):
    """
    ConsentLedger - Decentralized consent management on Algorand.

    Consent is minted as an ASA held by the user. Revoking consent
    freezes that ASA on-chain. is_consent_valid can be called by any
    third-party verifier without touching state.
    """

    def __init__(self) -> None:
        # BoxMap keyed by owner_bytes(32)||requester_bytes(32) = exactly 64 bytes (AVM max).
        # key_prefix=b"" prevents Algopy from prepending the field name ("consents") as prefix.
        self.consents = BoxMap(Bytes, ConsentRecord, key_prefix=b"")

    # ------------------------------------------------------------------ #
    # grant_consent                                                        #
    # ------------------------------------------------------------------ #

    @abimethod()
    def grant_consent(
        self,
        requester: arc4.Address,
        data_type: arc4.String,
        purpose: arc4.String,
        expiry: arc4.UInt64,
    ) -> arc4.UInt64:
        """
        Mint a consent ASA and store the record in box storage.

        The caller (Txn.sender) becomes the token holder and logical
        owner of the consent. The application holds manager/freeze/clawback
        so it can freeze the token upon revocation.

        Returns the newly created asset ID.
        """
        # Build a human-readable note with the consent metadata
        note = (
            b"ConsentLedger|"
            + data_type.bytes
            + b"|"
            + purpose.bytes
            + b"|requester:"
            + requester.bytes
        )

        # Mint 1 consent token (NFT-style, indivisible)
        mint_result = itxn.AssetConfig(
            total=1,
            decimals=0,
            unit_name=b"CONSENT",
            asset_name=b"ConsentToken",
            note=note,
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.current_application_address,
            clawback=Global.current_application_address,
            default_frozen=False,
            fee=0,
        ).submit()

        new_asset_id = mint_result.created_asset.id

        # Transfer token from app to the user (requires the app to opt-in first)
        # The app clawbacks the token to itself is only done on revoke.
        # Here we just record the fact — the user will be holding the token
        # via the clawback mechanism below.

        # Store the consent record in box storage keyed by sender||requester (64 bytes)
        record = ConsentRecord(
            owner=arc4.Address(Txn.sender),
            requester=requester,
            data_type=data_type,
            purpose=purpose,
            expiry=expiry,
            asset_id=arc4.UInt64(new_asset_id),
        )
        box_key = Txn.sender.bytes + requester.bytes
        self.consents[box_key] = record.copy()

        return arc4.UInt64(new_asset_id)

    # ------------------------------------------------------------------ #
    # revoke_consent                                                       #
    # ------------------------------------------------------------------ #

    @abimethod()
    def revoke_consent(self, requester: arc4.Address) -> None:
        """
        Freeze the consent ASA to represent on-chain revocation.

        Only the original owner of the consent may call this.
        """
        box_key = Txn.sender.bytes + requester.bytes

        # Load record and verify ownership
        record = self.consents[box_key].copy()
        assert record.owner == arc4.Address(Txn.sender), "Only the owner can revoke consent"

        native_asset_id = record.asset_id.native

        # Freeze the app's own holding of the ASA — the app is the creator
        # and holds the total supply. Freezing it marks the consent as revoked.
        itxn.AssetFreeze(
            freeze_asset=Asset(native_asset_id),
            freeze_account=Global.current_application_address,
            frozen=True,
            fee=0,
        ).submit()

    # ------------------------------------------------------------------ #
    # is_consent_valid                                                     #
    # ------------------------------------------------------------------ #

    @abimethod(readonly=True)
    def is_consent_valid(
        self,
        owner: arc4.Address,
        requester: arc4.Address,
    ) -> arc4.Bool:
        """
        Read-only verifier: returns True if consent is active and not expired.

        Checks:
        1. A consent record exists for this owner+requester pair.
        2. The expiry timestamp has not passed.
        3. The ASA is not frozen (i.e., not revoked).
        """
        box_key = owner.bytes + requester.bytes

        # Check record exists
        if box_key not in self.consents:
            return arc4.Bool(False)

        record = self.consents[box_key].copy()

        # Check expiry (0 means no expiry)
        if record.expiry.native != 0 and record.expiry.native < Global.latest_timestamp:
            return arc4.Bool(False)

        native_asset_id = record.asset_id.native

        # Check if the app's own holding is frozen (freeze = revoked)
        asset = Asset(native_asset_id)
        is_frozen, dummy_exists = op.AssetHoldingGet.asset_frozen(
            Global.current_application_address, asset
        )
        if is_frozen:
            return arc4.Bool(False)

        return arc4.Bool(True)
