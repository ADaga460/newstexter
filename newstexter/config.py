"""Load configuration from sources.yaml and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:  # optional in production (env vars may be injected by the host)
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = ROOT / "sources.yaml"

# Tier ordering, most to least urgent. Used for sorting and min_tier filtering.
TIERS = ["breaking", "high", "medium", "low"]
TIER_RANK = {tier: rank for rank, tier in enumerate(TIERS)}


@dataclass
class Feed:
    name: str
    url: str


@dataclass
class Settings:
    max_items: int = 5
    lookback_hours: int = 24
    one_message_per_item: bool = True
    min_tier: str = "low"
    digest_cron: str = "0 8 * * *"
    breaking_check_cron: str = ""
    editorial_voice: str = ""


@dataclass
class Config:
    feeds: list[Feed] = field(default_factory=list)
    recipients: list[str] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)

    # --- Environment-derived values ---
    @property
    def db_path(self) -> Path:
        raw = os.getenv("NEWSTEXTER_DB", "data/newstexter.db")
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path

    @property
    def twilio_from(self) -> str | None:
        return os.getenv("TWILIO_FROM_NUMBER")

    @property
    def skip_twilio_validation(self) -> bool:
        return os.getenv("NEWSTEXTER_SKIP_TWILIO_VALIDATION", "0") == "1"


def load_config(path: str | Path | None = None) -> Config:
    """Parse sources.yaml into a Config object."""
    path = Path(path) if path else DEFAULT_SOURCES
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    feeds = [Feed(name=f["name"], url=f["url"]) for f in data.get("feeds", [])]
    recipients = [str(r) for r in data.get("recipients", [])]
    settings = Settings(**(data.get("settings") or {}))

    if settings.min_tier not in TIER_RANK:
        raise ValueError(
            f"settings.min_tier must be one of {TIERS}, got {settings.min_tier!r}"
        )
    return Config(feeds=feeds, recipients=recipients, settings=settings)
