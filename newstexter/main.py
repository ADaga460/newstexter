"""Digest pipeline and CLI entry point.

  python -m newstexter.main --dry-run     # print, don't send
  python -m newstexter.main                # send the daily digest
  python -m newstexter.main --breaking     # send only breaking-tier stories
"""

from __future__ import annotations

import argparse
import hashlib
import logging

from .config import Config, load_config
from .curate import curate
from .fetch import fetch_candidates
from .format import build_messages, filter_by_min_tier, order_items
from .send import broadcast
from . import store

log = logging.getLogger(__name__)


def _hash(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def run_digest(
    config: Config | None = None,
    *,
    dry_run: bool = False,
    breaking_only: bool = False,
) -> int:
    """Run the full pipeline once. Returns the number of messages sent."""
    config = config or load_config()
    settings = config.settings

    with store.connect(config.db_path) as conn:
        candidates = fetch_candidates(
            config.feeds,
            lookback_hours=settings.lookback_hours,
            is_seen=lambda h: store.is_seen(conn, h),
        )
        items = curate(candidates, settings)

        if breaking_only:
            items = [it for it in items if it.tier == "breaking"]
        else:
            items = filter_by_min_tier(items, settings.min_tier)
        items = order_items(items)

        if not items:
            log.info("No stories to send after filtering.")
            return 0

        bodies = build_messages(items, one_per_item=settings.one_message_per_item)
        sent = broadcast(
            config.recipients,
            bodies,
            from_number=config.twilio_from,
            dry_run=dry_run,
        )

        # Record what we sent so it isn't repeated next run (skip in dry-run).
        if not dry_run:
            for it in items:
                store.mark_seen(conn, _hash(it.link))
        return sent


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsTexter digest runner")
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending")
    parser.add_argument("--breaking", action="store_true", help="send only breaking-tier stories")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_digest(dry_run=args.dry_run, breaking_only=args.breaking)


if __name__ == "__main__":
    main()
