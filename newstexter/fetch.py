"""Fetch and normalize RSS feeds: pull, recency-filter, and de-duplicate."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from .config import Feed

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class Article:
    title: str
    summary: str
    link: str
    source: str
    published: datetime | None

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.link.encode("utf-8")).hexdigest()


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _published(entry) -> datetime | None:
    """Best-effort published timestamp as an aware UTC datetime."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return None


def _entry_to_article(entry, source: str) -> Article | None:
    link = (entry.get("link") or "").strip()
    title = _clean(entry.get("title"))
    if not link or not title:
        return None
    return Article(
        title=title,
        summary=_clean(entry.get("summary") or entry.get("description")),
        link=link,
        source=source,
        published=_published(entry),
    )


def fetch_feed(feed: Feed) -> list[Article]:
    """Fetch a single feed, tolerating network/parse failures."""
    try:
        parsed = feedparser.parse(feed.url)
    except Exception as exc:  # feedparser rarely raises, but be safe
        log.warning("Failed to fetch %s: %s", feed.name, exc)
        return []
    if parsed.bozo and not parsed.entries:
        log.warning("Feed %s returned no usable entries (%s)", feed.name, parsed.bozo_exception)
        return []
    articles = []
    for entry in parsed.entries:
        article = _entry_to_article(entry, feed.name)
        if article:
            articles.append(article)
    return articles


def fetch_candidates(
    feeds: list[Feed],
    *,
    lookback_hours: int,
    is_seen=None,
) -> list[Article]:
    """Fetch all feeds, drop stale and already-seen items, de-dupe by URL.

    `is_seen` is an optional callable taking a url_hash and returning bool —
    used to skip stories already texted in a prior run.
    """
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - lookback_hours * 3600

    out: list[Article] = []
    seen_hashes: set[str] = set()
    for feed in feeds:
        for article in fetch_feed(feed):
            # Recency: keep items with no timestamp (can't tell) or within window.
            if article.published and article.published.timestamp() < cutoff:
                continue
            h = article.url_hash
            if h in seen_hashes:
                continue
            if is_seen and is_seen(h):
                continue
            seen_hashes.add(h)
            out.append(article)
    log.info("Fetched %d fresh candidate articles", len(out))
    return out
