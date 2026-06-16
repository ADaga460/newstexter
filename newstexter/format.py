"""Render curated items into SMS text: tier labels, ordering, and chunking."""

from __future__ import annotations

from .config import TIER_RANK
from .curate import CuratedItem

# Label shown at the start of each story.
TIER_LABEL = {
    "breaking": "🚨 BREAKING",
    "high": "🔴 HIGH",
    "medium": "🟠 MEDIUM",
    "low": "🟡 LOW",
}

# Conservative single-segment size; longer messages are concatenated by Twilio.
# Using the GSM-7 limit keeps chunk math simple even when emoji push a body into
# UCS-2 (Twilio still delivers, just as more segments).
CHUNK_SIZE = 1500


def order_items(items: list[CuratedItem]) -> list[CuratedItem]:
    """Sort breaking -> high -> medium -> low (stable within a tier)."""
    return sorted(items, key=lambda it: TIER_RANK[it.tier])


def filter_by_min_tier(items: list[CuratedItem], min_tier: str) -> list[CuratedItem]:
    threshold = TIER_RANK[min_tier]
    return [it for it in items if TIER_RANK[it.tier] <= threshold]


def render_item(item: CuratedItem) -> str:
    """One story as an SMS body: '[TIER] BLURB — summary  link'."""
    label = TIER_LABEL.get(item.tier, item.tier.upper())
    return f"{label}: {item.blurb}\n{item.summary}\n{item.link}"


def render_digest(items: list[CuratedItem]) -> str:
    """All stories combined into one message body."""
    return "\n\n".join(render_item(it) for it in items)


def render_comparison(items: list[CuratedItem]) -> str:
    """A numbered, human-readable list for the dry-run neutral comparison."""
    lines = []
    for i, it in enumerate(items, 1):
        label = TIER_LABEL.get(it.tier, it.tier.upper())
        lines.append(f"{i}. {label} ({it.source}) {it.blurb}\n   {it.summary}\n   {it.link}")
    return "\n\n".join(lines)


def chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split a long body into SMS-sized pieces, preferring paragraph/line breaks."""
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > size:
        window = remaining[:size]
        split = window.rfind("\n\n")
        if split <= 0:
            split = window.rfind("\n")
        if split <= 0:
            split = window.rfind(" ")
        if split <= 0:
            split = size
        chunks.append(remaining[:split].strip())
        remaining = remaining[split:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def build_messages(items: list[CuratedItem], *, one_per_item: bool) -> list[str]:
    """Produce the list of SMS bodies to send for a digest."""
    if not items:
        return []
    if one_per_item:
        bodies = [render_item(it) for it in items]
    else:
        bodies = [render_digest(items)]
    # Ensure nothing exceeds the chunk ceiling.
    out: list[str] = []
    for body in bodies:
        out.extend(chunk(body))
    return out
