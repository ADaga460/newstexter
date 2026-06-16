"""Tests for fetch normalization, recency, and de-duplication."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import feedparser

from newstexter import fetch
from newstexter.config import Feed


def _struct(dt: datetime):
    return dt.utctimetuple()


def _entry(title="T", link="https://example.com/a", published=None, summary="<p>body</p>"):
    e = feedparser.FeedParserDict()
    e["title"] = title
    e["link"] = link
    e["summary"] = summary
    if published is not None:
        e["published_parsed"] = _struct(published)
    return e


def test_entry_cleaning_strips_html():
    a = fetch._entry_to_article(_entry(summary="<b>Hello</b>   world"), "Src")
    assert a is not None
    assert a.summary == "Hello world"
    assert a.title == "T"
    assert a.source == "Src"


def test_entry_requires_title_and_link():
    assert fetch._entry_to_article(_entry(title=""), "Src") is None
    assert fetch._entry_to_article(_entry(link=""), "Src") is None


def test_recency_and_dedupe(monkeypatch):
    now = datetime.now(timezone.utc)
    fresh = _entry(link="https://example.com/fresh", published=now - timedelta(hours=1))
    stale = _entry(link="https://example.com/stale", published=now - timedelta(hours=48))
    dup_a = _entry(link="https://example.com/dup", published=now - timedelta(hours=2))
    dup_b = _entry(link="https://example.com/dup", published=now - timedelta(hours=2))
    no_date = _entry(link="https://example.com/nodate", published=None)

    feed = Feed(name="F", url="https://example.com/feed")

    def fake_fetch_feed(_feed):
        return [
            fetch._entry_to_article(e, "F")
            for e in (fresh, stale, dup_a, dup_b, no_date)
        ]

    monkeypatch.setattr(fetch, "fetch_feed", fake_fetch_feed)

    out = fetch.fetch_candidates([feed], lookback_hours=24)
    links = {a.link for a in out}

    assert "https://example.com/fresh" in links      # within window
    assert "https://example.com/nodate" in links     # undated kept
    assert "https://example.com/stale" not in links  # too old
    assert sum(a.link.endswith("/dup") for a in out) == 1  # de-duped


def test_is_seen_skips(monkeypatch):
    now = datetime.now(timezone.utc)
    a = _entry(link="https://example.com/seen", published=now)
    feed = Feed(name="F", url="https://example.com/feed")
    monkeypatch.setattr(fetch, "fetch_feed", lambda _f: [fetch._entry_to_article(a, "F")])

    out = fetch.fetch_candidates([feed], lookback_hours=24, is_seen=lambda h: True)
    assert out == []
