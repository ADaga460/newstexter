"""Handle inbound SMS: answer questions with Claude + the web_search tool.

Grounding answers in live web search is what makes replies accurate and current
rather than guesses. Only allowlisted numbers are answered (enforced by caller).
"""

from __future__ import annotations

import logging

import anthropic

from . import MODEL
from .config import Settings

log = logging.getLogger(__name__)

MAX_CONTINUATIONS = 5

_SYSTEM_TEMPLATE = """\
You are NewsTexter, a personal news assistant that replies over SMS. You also
send a daily digest of under-covered international news; this is the inbound
reply channel where the user asks follow-up questions.

- Answer accurately. For anything that depends on current or recent information
  (events, prices, who holds an office, latest developments), use the web_search
  tool before answering rather than relying on memory. Ground claims in what you
  find; do not fabricate.
- Keep replies SMS-length: tight and direct, a few sentences at most. No markdown
  headers or bullet characters that read poorly on a phone.
- Apply this editorial voice when it's relevant to the question:
{voice}"""

_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


def _extract_text(content) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()


def answer(
    user_text: str,
    settings: Settings,
    *,
    history: list[dict] | None = None,
    client: anthropic.Anthropic | None = None,
) -> str:
    """Produce a reply to an inbound message, using web search for grounding."""
    client = client or anthropic.Anthropic()
    system = _SYSTEM_TEMPLATE.format(voice=settings.editorial_voice.strip())

    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": user_text})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        thinking={"type": "adaptive"},
        system=system,
        tools=[_WEB_SEARCH_TOOL],
        messages=messages,
    )

    # Server-side web search may pause to continue its own loop; resume it.
    continuations = 0
    while response.stop_reason == "pause_turn" and continuations < MAX_CONTINUATIONS:
        messages.append({"role": "assistant", "content": response.content})
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            system=system,
            tools=[_WEB_SEARCH_TOOL],
            messages=messages,
        )
        continuations += 1

    text = _extract_text(response.content)
    return text or "Sorry — I couldn't put together an answer to that. Try rephrasing?"
