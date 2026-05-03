import asyncio
import logging
import sys
from contextlib import suppress

import uvicorn

from settings import settings


async def main() -> None:
    config = uvicorn.Config(
        "server:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        use_colors=True,
        log_level="debug" if settings.DEBUG else "info",
        server_header=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)

    with suppress(KeyboardInterrupt):
        if sys.platform in ("linux", "darwin"):
            import uvloop

            uvloop.run(main())
        else:
            asyncio.run(main())
