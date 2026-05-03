import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import QwenParser, ingest_channel


async def _run() -> None:
    p = argparse.ArgumentParser(description="Pull recent posts from a Telegram channel and upsert them as Listings")
    p.add_argument("channel_id", type=int, nargs="?", default=1525185710,
                   help="Bare channel ID (without the -100 prefix). Default: 1525185710")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--dry-run", action="store_true", help="Parse and log without writing to MongoDB")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    n = await ingest_channel(QwenParser(), args.channel_id, args.limit, args.dry_run)
    verb = "would insert" if args.dry_run else "inserted"
    logging.info("done — %s %d listing(s)", verb, n)


if __name__ == "__main__":
    asyncio.run(_run())
