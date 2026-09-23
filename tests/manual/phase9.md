# Phase 9 — Manual Tests (Google)

Set up once: `.venv\Scripts\python.exe scripts\google_login.py`

| ID | Say | Expected | Result |
|---|---|---|---|
| TEST 090 | "What meetings do I have today?" | Reads your real calendar (or "nothing today") | |
| TEST 091 | "What's on my calendar tomorrow?" | Tomorrow's meetings | |
| TEST 092 | "Schedule a meeting with Rahul tomorrow at 3 PM about the loan model" | Asks "Should I schedule…?" → say yes → event created with a Google Meet link and Rahul invited | |
| TEST 093 | "What's Rahul's email?" | Reads it from your contacts | |
| TEST 094 | "Any new emails?" | Lists unread senders and subjects | |
| TEST 095 | "Read the one from Rahul" | Reads/summarises it | |
| TEST 096 | "Reply saying 4 PM works for me" | Asks with the exact text → say yes → reply sent in the same thread | |
| TEST 097 | "Send an email to Rahul saying the model is ready" | Asks first, then sends | |
| TEST 098 | Wake JARVIS in the morning | Briefing says "You have N meetings today: …" | |
