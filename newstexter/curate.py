"""Curate fetched articles with Gemini: select, tier, and write framed blurbs.

A single Gemini call takes the candidate articles and returns the most important
/ under-covered stories, each with an importance tier and a short blurb + 2-4
sentence summary written in the configured editorial voice. The model selects by
index so it can never invent a link.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from . import MODEL
from .config import Settings
from .fetch import Article
from .llm import get_client

log = logging.getLogger(__name__)

Tier = Literal["breaking", "high", "medium", "low"]

_SYSTEM = """\
You are the editor of a personal SMS news digest that surfaces important but
UNDER-COVERED international news — stories major Western outlets tend to skip.

Your job, given a list of candidate articles (each with an index, source, title,
and summary):
1. Select the most internationally important and under-covered stories, up to the
   requested maximum. Prefer global-south, labor, human-rights, environmental,
   and political-economy stories over celebrity, sports, or domestic-trivia items.
   Skip anything already well-saturated in mainstream coverage.
2. Assign each an importance tier by genuine global significance and urgency:
   - breaking: major, time-sensitive developing event of clear international weight
   - high:     very important, widely consequential
   - medium:   notable and worth knowing
   - low:      interesting context, lower stakes
3. Write for each:
   - blurb: a 3-6 word headline-style hook
   - summary: 2-4 sentences in the editorial voice below

Editorial voice:
{voice}

Hard rule: stay rigorously faithful to what the source article actually reports.
Do NOT invent facts, numbers, quotes, or events. If the candidate summary is
thin, write a shorter, more general summary rather than fabricating detail.
Select by the article's `index`. Return only your selections."""


class Selection(BaseModel):
    index: int = Field(description="The candidate article's index.")
    tier: Tier
    blurb: str = Field(description="A 3-6 word headline-style hook.")
    summary: str = Field(description="2-4 sentence summary in the editorial voice.")


class Curation(BaseModel):
    items: list[Selection]


@dataclass
class CuratedItem:
    tier: Tier
    blurb: str
    summary: str
    link: str
    source: str


def _render_candidates(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles):
        summary = a.summary[:600]
        lines.append(f"[{i}] ({a.source}) {a.title}\n{summary}")
    return "\n\n".join(lines)


def curate(
    articles: list[Article],
    settings: Settings,
    *,
    client=None,
) -> list[CuratedItem]:
    """Return curated, tiered items. Empty input yields an empty result."""
    if not articles:
        return []

    from google.genai import types

    client = client or get_client()
    system = _SYSTEM.format(voice=settings.editorial_voice.strip())
    user = (
        f"Select up to {settings.max_items} stories from these "
        f"{len(articles)} candidates:\n\n{_render_candidates(articles)}"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=Curation,
            temperature=0.3,
        ),
    )

    curation = response.parsed
    if curation is None:
        log.warning("Curation returned no parseable output.")
        return []

    items: list[CuratedItem] = []
    for sel in curation.items:
        if not 0 <= sel.index < len(articles):
            log.warning("Curator returned out-of-range index %d; skipping", sel.index)
            continue
        article = articles[sel.index]
        items.append(
            CuratedItem(
                tier=sel.tier,
                blurb=sel.blurb.strip(),
                summary=sel.summary.strip(),
                link=article.link,
                source=article.source,
            )
        )
    log.info("Curated %d items from %d candidates", len(items), len(articles))
    return items
