import logging

import algokit_utils

logger = logging.getLogger(__name__)


def deploy() -> None:
    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")

    try:
        from smart_contracts.artifacts.org_registry.org_registry_contract_client import (
            OrgRegistryContractFactory,
        )
    except ImportError:
        logger.warning(
            "OrgRegistryContract client not yet generated — run `algokit project run build` first."
        )
        return

    factory = algorand.client.get_typed_app_factory(
        OrgRegistryContractFactory, default_sender=deployer.address
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount(micro_algo=300_000),
                sender=deployer.address,
                receiver=app_client.app_address,
            )
        )
        logger.info(f"Funded OrgRegistry account {app_client.app_address} with 0.3 ALGO")

    logger.info(
        f"OrgRegistryContract deployed: app_id={app_client.app_id}, "
        f"app_address={app_client.app_address}"
    )
