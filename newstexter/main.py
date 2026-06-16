"""Poll cycle (per-story delivery) and CLI entry point.

  python -m newstexter.main --dry-run     # preview curation, send nothing
  python -m newstexter.main                # run one live poll cycle now

The scheduled service (newstexter.app) runs `run_cycle` every few minutes so new
stories are texted out individually as they appear — not batched into a digest.
"""

from __future__ import annotations

import argparse
import logging

from .config import Config, load_config
from .curate import curate
from .fetch import fetch_candidates
from .format import build_messages, filter_by_min_tier, order_items, render_comparison
from .send import broadcast, _safe_print
from . import store

log = logging.getLogger(__name__)


def run_cycle(config: Config | None = None, *, dry_run: bool = False) -> int:
    """One poll cycle: text any newly-appeared qualifying stories, one per story.

    Returns the number of messages sent. On the very first run (empty DB) it
    seeds existing stories as 'seen' WITHOUT sending, so deploying doesn't blast
    a backlog — only stories that break afterward get texted.
    """
    config = config or load_config()
    settings = config.settings

    with store.connect(config.db_path) as conn:
        candidates = fetch_candidates(
            config.feeds,
            lookback_hours=settings.lookback_hours,
            is_seen=lambda h: store.is_seen(conn, h),
        )
        if not candidates:
            log.info("No new stories this cycle.")
            return 0

        # Cold start: seed without sending so we don't blast 24h of backlog.
        if not dry_run and store.is_empty(conn):
            for a in candidates:
                store.mark_seen(conn, a.url_hash)
            log.info(
                "Seeded %d existing stories; new stories will be texted as they appear.",
                len(candidates),
            )
            return 0

        items = order_items(
            filter_by_min_tier(curate(candidates, settings), settings.min_tier)
        )
        bodies = build_messages(items, one_per_item=settings.one_message_per_item)
        sent = broadcast(
            config.recipients,
            bodies,
            from_number=config.twilio_from,
            dry_run=dry_run,
        )

        # Each candidate considered this cycle is marked seen so it's evaluated
        # exactly once (no re-sends, no pile-up). Skip in dry-run.
        if not dry_run:
            for a in candidates:
                store.mark_seen(conn, a.url_hash)
        return sent


def preview(config: Config | None = None) -> None:
    """Dry-run tuning view: show the slanted picks + a neutral comparison.

    Ignores the seen-DB and sends nothing — purely for checking the curation and
    voice against current feeds.
    """
    config = config or load_config()
    settings = config.settings

    candidates = fetch_candidates(config.feeds, lookback_hours=settings.lookback_hours)
    items = order_items(filter_by_min_tier(curate(candidates, settings), settings.min_tier))
    bodies = build_messages(items, one_per_item=settings.one_message_per_item)
    broadcast(config.recipients, bodies, from_number=None, dry_run=True)

    neutral = order_items(curate(candidates, settings, neutral=True, limit=settings.max_items))
    _safe_print(
        f"\n===== NEUTRAL TOP {settings.max_items} "
        "(pure-neutral comparison — not part of what gets sent) ====="
    )
    _safe_print(render_comparison(neutral) if neutral else "(none)")


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsTexter")
    parser.add_argument(
        "--dry-run", action="store_true", help="preview curation; send nothing"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.dry_run:
        preview()
    else:
        run_cycle()


if __name__ == "__main__":
    main()
