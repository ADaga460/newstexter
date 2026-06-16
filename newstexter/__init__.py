"""NewsTexter — aggregate under-covered international news and text it out."""

__version__ = "0.1.0"

# The Gemini model used for curation and inbound replies. Configurable here.
# gemini-2.5-flash is on the free tier and supports structured output + Google
# Search grounding. gemini-2.5-flash-lite is a cheaper/faster free alternative.
MODEL = "gemini-2.5-flash"
