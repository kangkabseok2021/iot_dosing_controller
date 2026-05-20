from .client import OrchestratorClient


class FaultInjector:
    def __init__(self, client: OrchestratorClient) -> None:
        self._client = client

    async def inject(self, fault_type: str, params: dict | None = None) -> None:
        raise NotImplementedError(fault_type)
