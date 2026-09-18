from __future__ import annotations

import asyncio
import logging
import sys

from control_panel.settings import get_settings
from control_panel.supervisor import Supervisor


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


async def amain() -> None:
    settings = get_settings()
    if not settings.subscription_url:
        raise SystemExit("SUBSCRIPTION_URL is required")
    supervisor = Supervisor(settings)
    await supervisor.run()


def main() -> None:
    setup_logging()
    asyncio.run(amain())


if __name__ == "__main__":
    main()
