"""NewsTexter — aggregate under-covered international news and text it out."""

__version__ = "0.1.0"

# The Gemini model used for curation and inbound replies. Configurable here.
# gemini-2.0-flash is fast and on the free tier. gemini-2.5-flash also works if
# you want a bit more quality (still free tier).
MODEL = "gemini-2.0-flash"
