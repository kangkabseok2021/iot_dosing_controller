"""Entry point for running the ForecastWorker as a standalone process."""

import asyncio
import signal

from loguru import logger

from app.workers.forecaster import ForecastWorker


async def main() -> None:
    worker = ForecastWorker()
    loop = asyncio.get_running_loop()

    def _shutdown(sig):
        logger.info("Received {}, stopping worker", sig.name)
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    await worker.start()
    await worker._stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
