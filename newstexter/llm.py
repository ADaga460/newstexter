"""Shared Google Gemini client factory."""

from __future__ import annotations

import os


def get_client():
    """Return a configured google-genai client.

    Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment. Get a free
    key at https://aistudio.google.com/apikey
    """
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)
