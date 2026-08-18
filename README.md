# Northstar Homes conversational sales bot

A simple FastAPI web app for **Northstar One, Sector 79, Gurugram**. It demonstrates a bilingual (English/Hindi/Hinglish) AI sales agent that qualifies leads, handles objections and consent, simulates site-visit outcomes, maintains session memory, and produces lead analytics.

## Requirements coverage

- Final channel-neutral prompt: [PROMPT.md](PROMPT.md), designed for both chat and voice.
- FastAPI/Python backend only; no Express or other backend framework.
- In-memory conversation memory, safety-first deterministic actions, and OpenAI Responses API generation.
- Site visit request and explicit failure handling (a request containing `unavailable`, `slot full`, or `failure` demonstrates failure; the agent never calls it confirmed).
- Analytics: configuration, budget, intent/purpose, interest, visit state, requested time, follow-up, escalation, DNC, and message count.
- Reviewable test scenarios with input, expected behavior, and actual output: [TEST_CASES.md](TEST_CASES.md). Automated checks live in `tests/`.

## Run locally

Prerequisite: Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env.local
# Set OPENAI_API_KEY locally in .env.local (never commit this file)
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. End a conversation to view generated analytics. Run tests with:

```powershell
pytest -q
```

To demo the safe local fallback without making an API request, run PowerShell with `$env:NORTHSTAR_OFFLINE='1'` before starting the server.

## Prompt approach

The system prompt uses a fact allowlist, so the agent only states the supplied location, configurations, and starting prices. It provides channel rules (short spoken turns for calls), language mirroring, consent/DNC behavior, a practical qualification sequence, safe unknown-question language, and tool-result-only booking confirmation. The application adds three guardrails beyond the prompt:

1. **Pre-routing** — price, project-overview, and unknown-detail questions are answered from deterministic templates instead of the model.
2. **Structured facts in context** — every API call receives an explicit `AUTHORITATIVE_FACTS_ONLY` object the model must not exceed.
3. **Output sanitization** — if the model invents prices, amenities, possession details, or false booking confirmations, the reply is replaced with a safe fallback.

## Key assumptions

- This is a demo: conversations live in process memory and reset when the server restarts.
- A real booking service would replace the simulated booking state and return the actual confirmed slot.
- The API key is local-only in `.env.local`; `.env.example` contains no secret.
- `OPENAI_MODEL` defaults to `gpt-5.6` and can be changed locally.

## Known limitations

- No authentication, CRM, persistent database, telephony, or real calendar integration.
- The UI is text-only; the prompt is voice-ready but speech-to-text/text-to-speech is intentionally out of scope.
- If OpenAI is unavailable, the app uses a small deterministic fallback to preserve the required demo flows.

## AI tools used

- OpenAI Responses API via the official Python SDK for conversational generation.
- The system prompt and safety rules are included in this repository for review.

## Demo video and submission

Record a 2–3 minute Loom/Drive/unlisted YouTube walkthrough showing a normal conversation, a booking failure, the prompt, and the analytics. Add its public link below before emailing the assignment.

```text
Repository: <public GitHub URL>
Demo video: <public video URL>
```

Suggested email recipients: `aditi@huvo.ai` (To); `nikhil@huvo.ai`, `vaibhav@huvo.ai`, and `rohit@huvo.ai` (CC).
