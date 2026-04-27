from algopy import (
    ARC4Contract,
    BoxMap,
    Bytes,
    Global,
    Txn,
    arc4,
)
from algopy.arc4 import abimethod


class OrgRecord(arc4.Struct):
    name: arc4.String
    dpdp_license: arc4.String   # DPDP Data Fiduciary registration number
    allowed_types: arc4.UInt16  # bitmask: bit0=name, bit1=dob, bit2=address, ...
    x402_wallet: arc4.Address   # wallet used for x402 consent fee payments
    is_active: arc4.Bool


class OrgRegistryContract(ARC4Contract):
    """
    Whitelist registry for DPDP Act Data Fiduciaries (Data Processors).

    Only admin-registered organisations can request consent in ConsentLedger.
    Each org carries a bitmask of allowed data field types and a DPDP license number.
    The contract creator is the permanent admin.
    """

    def __init__(self) -> None:
        # Box key = org_address.bytes(32). Prefix(4) + key(32) = 36 bytes total.
        self.orgs = BoxMap(Bytes, OrgRecord, key_prefix=b"org_")

    @abimethod()
    def register_org(
        self,
        org_address: arc4.Address,
        name: arc4.String,
        dpdp_license: arc4.String,
        allowed_types: arc4.UInt16,
        x402_wallet: arc4.Address,
    ) -> None:
        """Register a new Data Fiduciary. Only the contract creator (admin) can call this."""
        assert Txn.sender == Global.creator_address, "Only admin can register organisations"
        key = org_address.bytes
        record = OrgRecord(
            name=name,
            dpdp_license=dpdp_license,
            allowed_types=allowed_types,
            x402_wallet=x402_wallet,
            is_active=arc4.Bool(True),
        )
        self.orgs[key] = record.copy()

    @abimethod()
    def deactivate_org(self, org_address: arc4.Address) -> None:
        """Deactivate an organisation. Only the contract creator (admin) can call this."""
        assert Txn.sender == Global.creator_address, "Only admin can deactivate organisations"
        key = org_address.bytes
        assert key in self.orgs, "Organisation not found"
        record = self.orgs[key].copy()
        self.orgs[key] = OrgRecord(
            name=record.name,
            dpdp_license=record.dpdp_license,
            allowed_types=record.allowed_types,
            x402_wallet=record.x402_wallet,
            is_active=arc4.Bool(False),
        ).copy()

    @abimethod(readonly=True)
    def is_org_authorized(
        self,
        org: arc4.Address,
        requested_field_mask: arc4.UInt16,
    ) -> arc4.Bool:
        """
        Check whether an org is active and authorised for the requested data fields.
        requested_field_mask must be a non-empty subset of the org's allowed_types bitmask.
        """
        key = org.bytes
        if key not in self.orgs:
            return arc4.Bool(False)
        record = self.orgs[key].copy()
        if not record.is_active.native:
            return arc4.Bool(False)
        allowed = record.allowed_types.native
        requested = requested_field_mask.native
        # All requested bits must be set in allowed, and request must not be empty
        return arc4.Bool(requested != 0 and (allowed & requested) == requested)

    @abimethod(readonly=True)
    def get_org_record(self, org: arc4.Address) -> OrgRecord:
        """Read-only: returns the org record for the given address."""
        key = org.bytes
        assert key in self.orgs, "Organisation not found"
        return self.orgs[key].copy()
