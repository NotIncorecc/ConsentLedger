import logging
import os

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    try:
        from smart_contracts.artifacts.zk_verifier.zk_verifier_contract_client import (
            ZkVerifierContractFactory,
        )
    except ImportError:
        logger.warning(
            "ZKVerifierContract client not yet generated — run `algokit project run build` first."
        )
        return

    factory = algorand.client.get_typed_app_factory(
        ZkVerifierContractFactory, default_sender=deployer.address
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        logger.info(
            f"ZKVerifier created at {app_client.app_address} — fund manually via testnet faucet before use"
        )

    # Link to ConsentLedger if app_id is provided via env var
    consent_ledger_app_id = int(os.environ.get("CONSENT_LEDGER_APP_ID", "0"))
    if consent_ledger_app_id > 0:
        app_client.send.set_consent_ledger_app(args=(consent_ledger_app_id,))
        logger.info(f"ZKVerifier linked to ConsentLedger app_id={consent_ledger_app_id}")

    logger.info(
        f"ZKVerifierContract deployed: app_id={app_client.app_id}, "
        f"app_address={app_client.app_address}"
    )
