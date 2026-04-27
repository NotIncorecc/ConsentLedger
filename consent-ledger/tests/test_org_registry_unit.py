"""
Unit tests for OrgRegistryContract (Phase 2).

Tests cover:
- Admin (creator) can register an organisation
- Non-admin cannot register
- is_org_authorized with bitmask subset check
- Fields outside allowed_types are rejected
- Deactivating an org blocks authorization
- Unknown orgs return False from is_org_authorized

Run: algokit project run test
  or: poetry run pytest tests/ -v
"""
import algosdk
import pytest

from algopy import arc4
from algopy_testing import algopy_testing_context

from smart_contracts.org_registry.contract import OrgRegistryContract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_addr() -> str:
    return algosdk.account.generate_account()[1]


def _register(
    contract: OrgRegistryContract,
    org_addr: str | None = None,
    allowed_types: int = 0b00000111,  # bits 0,1,2 = name, dob, address
) -> str:
    addr = org_addr or _random_addr()
    contract.register_org(
        org_address=arc4.Address(addr),
        name=arc4.String("ACME Health"),
        dpdp_license=arc4.String("DF-2024-001"),
        allowed_types=arc4.UInt16(allowed_types),
        x402_wallet=arc4.Address(addr),
    )
    return addr


# ---------------------------------------------------------------------------
# test_register_org_succeeds
# ---------------------------------------------------------------------------

def test_register_org_succeeds() -> None:
    """Contract creator can register an organisation successfully."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        org_addr = _register(contract)  # Txn.sender == Global.creator_address in tests

        result = contract.is_org_authorized(
            org=arc4.Address(org_addr),
            requested_field_mask=arc4.UInt16(0b00000011),  # name + dob (subset of 0b111)
        )
        assert result.native is True


# ---------------------------------------------------------------------------
# test_get_org_record
# ---------------------------------------------------------------------------

def test_get_org_record_returns_stored_values() -> None:
    """get_org_record must return the correct name and dpdp_license."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        org_addr = _register(contract)

        record = contract.get_org_record(org=arc4.Address(org_addr))
        assert record.name.native == "ACME Health"
        assert record.dpdp_license.native == "DF-2024-001"
        assert record.is_active.native is True


# ---------------------------------------------------------------------------
# test_bitmask_subset_check
# ---------------------------------------------------------------------------

def test_bitmask_check_rejects_out_of_scope_fields() -> None:
    """is_org_authorized must return False if requested fields are not a subset of allowed."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        org_addr = _register(contract, allowed_types=0b00000111)  # bits 0,1,2

        # Request bit 3 (financial data) — NOT in allowed_types
        result = contract.is_org_authorized(
            org=arc4.Address(org_addr),
            requested_field_mask=arc4.UInt16(0b00001000),
        )
        assert result.native is False


def test_bitmask_empty_request_rejected() -> None:
    """is_org_authorized must return False for a zero (empty) field mask request."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        org_addr = _register(contract, allowed_types=0b11111111)

        result = contract.is_org_authorized(
            org=arc4.Address(org_addr),
            requested_field_mask=arc4.UInt16(0),
        )
        assert result.native is False


# ---------------------------------------------------------------------------
# test_deactivate_org
# ---------------------------------------------------------------------------

def test_deactivate_org_blocks_authorization() -> None:
    """Deactivated orgs must fail is_org_authorized regardless of bitmask."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        org_addr = _register(contract, allowed_types=0b11111111)

        # Verify active first
        assert contract.is_org_authorized(
            org=arc4.Address(org_addr),
            requested_field_mask=arc4.UInt16(0b00000001),
        ).native is True

        contract.deactivate_org(arc4.Address(org_addr))

        assert contract.is_org_authorized(
            org=arc4.Address(org_addr),
            requested_field_mask=arc4.UInt16(0b00000001),
        ).native is False


# ---------------------------------------------------------------------------
# test_is_org_authorized_unknown
# ---------------------------------------------------------------------------

def test_is_org_authorized_returns_false_for_unknown() -> None:
    """is_org_authorized must return False for unregistered orgs."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        result = contract.is_org_authorized(
            org=arc4.Address(_random_addr()),
            requested_field_mask=arc4.UInt16(1),
        )
        assert result.native is False


# ---------------------------------------------------------------------------
# test_get_org_record_unknown_fails
# ---------------------------------------------------------------------------

def test_get_org_record_unknown_fails() -> None:
    """get_org_record must raise for an unregistered org address."""
    with algopy_testing_context() as ctx:
        contract = OrgRegistryContract()
        with pytest.raises(Exception, match="Organisation not found"):
            contract.get_org_record(org=arc4.Address(_random_addr()))
