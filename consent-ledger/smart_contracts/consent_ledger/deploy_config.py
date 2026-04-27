import logging

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    # Import the generated factory (created after first build)
    try:
        from smart_contracts.artifacts.consent_ledger.consent_ledger_client import (
            ConsentLedgerFactory,
        )
    except ImportError:
        logger.warning("ConsentLedger client not yet generated — run `algokit project run build` first.")
        return

    factory = algorand.client.get_typed_app_factory(
        ConsentLedgerFactory, default_sender=deployer.address
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    # Fund the app account so it can pay MBR for box storage and inner txns
    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        logger.info(
            f"ConsentLedger created at {app_client.app_address} — fund manually via testnet faucet before use"
        )

    logger.info(
        f"ConsentLedger deployed: app_id={app_client.app_id}, "
        f"app_address={app_client.app_address}"
    )
