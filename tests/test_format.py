"""Tests for tier ordering, filtering, rendering, and chunking."""

from __future__ import annotations

from newstexter.curate import CuratedItem
from newstexter import format as fmt


def _item(tier, blurb="Blurb", summary="Summary.", link="https://x/y", source="Src"):
    return CuratedItem(tier=tier, blurb=blurb, summary=summary, link=link, source=source)


def test_order_breaking_first():
    items = [_item("low"), _item("breaking"), _item("medium"), _item("high")]
    ordered = fmt.order_items(items)
    assert [it.tier for it in ordered] == ["breaking", "high", "medium", "low"]


def test_filter_by_min_tier():
    items = [_item("breaking"), _item("high"), _item("medium"), _item("low")]
    kept = fmt.filter_by_min_tier(items, "high")
    assert [it.tier for it in kept] == ["breaking", "high"]


def test_render_item_contains_parts():
    body = fmt.render_item(_item("breaking", blurb="Coup in Xland", link="https://l/1"))
    assert "BREAKING" in body
    assert "Coup in Xland" in body
    assert "https://l/1" in body


def test_build_messages_one_per_item():
    items = [_item("high"), _item("low")]
    msgs = fmt.build_messages(items, one_per_item=True)
    assert len(msgs) == 2


def test_build_messages_combined():
    items = [_item("high"), _item("low")]
    msgs = fmt.build_messages(items, one_per_item=False)
    assert len(msgs) == 1
    assert "HIGH" in msgs[0] and "LOW" in msgs[0]


def test_chunk_splits_long_text():
    text = "\n\n".join(f"paragraph {i} " + "x" * 100 for i in range(40))
    chunks = fmt.chunk(text, size=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_short_text_single():
    assert fmt.chunk("hello", size=500) == ["hello"]
