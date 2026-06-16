# NewsTexter

Aggregates **under-covered but important international news** — the kind major
outlets skip — and texts it to a small set of phone numbers as short, tiered
items (blurb + 2–4 sentence summary + link). It's also **two-way**: text the bot
a question and it replies with current, web-grounded info.

- **Sources** are curated toward independent / global-south / left-leaning outlets
  (no right-leaning feeds) — see [`sources.yaml`](sources.yaml).
- **Summaries** are written in a critical / anti-capitalist editorial voice while
  staying factually faithful to the source.
- **Tiers**: every story is labeled `breaking` / `high` / `medium` / `low` and
  ordered breaking-first.
- **Curation + replies** use Google **Gemini** (`gemini-2.5-flash`, free tier);
  replies are grounded with Gemini's built-in Google Search.

## How it works

One always-on FastAPI process does two things:

1. **Story polling** (APScheduler): every few minutes, fetch RSS → keep only
   newly-published stories (the seen-DB dedupes) → Gemini selects, tiers, and
   writes the worthy ones → text them out **individually, as they appear**. On
   first run it seeds existing stories without sending, so you only get news that
   breaks afterward — never a backlog blast.
2. **Inbound replies** (`POST /sms`): a Twilio webhook routes texts from
   allowlisted numbers to Gemini (+ Google Search grounding), with short
   per-number history.

```
newstexter/
  config.py   fetch.py   curate.py   format.py
  send.py     reply.py   store.py    app.py   main.py
```

## Cost

Built to run **free**. Gemini's free tier ([aistudio.google.com](https://aistudio.google.com/apikey))
covers frequent polling and replies — a Gemini call only happens on cycles that
actually find new stories, so most polls are free RSS fetches with no model call.
The only thing you may pay for is Twilio SMS (a few cents per message) and, in
the US, the one-time A2P/Toll-Free registration. If you ever bump into free-tier
limits, widen `poll_interval_minutes` in `sources.yaml`, or bump `MODEL` /
add billing in AI Studio.

## Setup

1. **Install**
   ```sh
   pip install -r requirements.txt
   ```
2. **Configure** — copy `.env.example` to `.env` and fill in:
   - `GEMINI_API_KEY` — free key from https://aistudio.google.com/apikey
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
   Add your phone number(s) to `recipients:` in `sources.yaml` (this is also the
   inbound allowlist).
3. **Twilio number** — buy a number, and point its *"A message comes in"* webhook
   to `https://<your-host>/sms`. Note: delivering to **US** numbers requires a
   one-time Toll-Free verification or A2P 10DLC registration (a form in the
   Twilio console) before messages will go through.

## Run

```sh
# Preview curation (slanted picks + a neutral comparison); sends nothing:
python -m newstexter.main --dry-run

# Run one live poll cycle now (texts any new stories since last run):
python -m newstexter.main

# Run the always-on service — polls every poll_interval_minutes + serves /sms:
uvicorn newstexter.app:app --host 0.0.0.0 --port 8000
```

Stories are texted **per story, as they appear** — there's no nightly batch.
Tune cadence and volume in `sources.yaml`: `poll_interval_minutes` (how often to
check), `max_items` (cap per check), and `min_tier` (raise to `medium`/`high` to
cut noise).

### Testing inbound replies locally

```sh
# 1. Run the service with signature validation off (LOCAL ONLY):
NEWSTEXTER_SKIP_TWILIO_VALIDATION=1 uvicorn newstexter.app:app --port 8000
# 2. Expose it:  ngrok http 8000
# 3. Point the Twilio number's inbound webhook at https://<ngrok>/sms
# 4. Text a question from an allowlisted number.
```

## Deploy (always-on)

Any host that runs a long-lived Python web process with a persistent disk works
(Render / Railway / Fly). Provide the env vars as host secrets, mount a volume
for `data/` (the SQLite DB — de-dupe state + chat history), and run
`uvicorn newstexter.app:app --host 0.0.0.0 --port $PORT`. The scheduler runs
inside this process, so no separate cron is needed.

## Tests

```sh
pytest
```

Covers fetch recency/de-dupe and format tier-ordering/chunking offline (no
network, no API keys).
