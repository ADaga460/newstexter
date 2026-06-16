"""Handle inbound SMS: answer questions with Gemini + Google Search grounding.

Gemini's built-in Google Search grounding is what makes replies accurate and
current rather than guesses — no separate search API needed. Only allowlisted
numbers are answered (enforced by the caller).
"""

from __future__ import annotations

import logging

from . import MODEL
from .config import Settings
from .llm import get_client

log = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
You are NewsTexter, a personal news assistant that replies over SMS. You also
text out important, under-covered international news stories as they break; this
is the inbound reply channel where the user asks follow-up questions.

- Answer accurately. For anything that depends on current or recent information
  (events, prices, who holds an office, latest developments), use Google Search
  to ground your answer rather than relying on memory. Do not fabricate.
- Keep replies SMS-length: tight and direct, a few sentences at most. No markdown
  headers or bullet characters that read poorly on a phone.
- Apply this editorial voice when it's relevant to the question:
{voice}"""


def _to_contents(history: list[dict], user_text: str):
    """Map stored history (+ the new message) into Gemini Content objects.

    Stored roles are 'user' / 'assistant'; Gemini expects 'user' / 'model'.
    """
    from google.genai import types

    contents = []
    for m in history or []:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
    return contents


def answer(
    user_text: str,
    settings: Settings,
    *,
    history: list[dict] | None = None,
    client=None,
) -> str:
    """Produce a reply to an inbound message, grounded via Google Search."""
    from google.genai import types

    client = client or get_client()
    system = _SYSTEM_TEMPLATE.format(voice=settings.editorial_voice.strip())

    response = client.models.generate_content(
        model=MODEL,
        contents=_to_contents(history or [], user_text),
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.4,
        ),
    )

    text = (response.text or "").strip()
    return text or "Sorry — I couldn't put together an answer to that. Try rephrasing?"
