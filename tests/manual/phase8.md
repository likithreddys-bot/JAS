# Phase 8 — Manual Tests (Reminders)

| ID | Say | Expected | Result |
|---|---|---|---|
| TEST 080 | "Remind me in 2 minutes to drink water" | "I've set a reminder…"; after 2 min: 🔔 notification **and** JARVIS says "Likki, reminder: drink water" | |
| TEST 081 | "Remind me at 9 PM to call Rahul" | Confirms the exact time (tonight, not tomorrow) | |
| TEST 082 | "Remind me every weekday at 10 AM about the standup" | Confirms it repeats on weekdays | |
| TEST 083 | "What reminders do I have?" | Lists them with times | |
| TEST 084 | "Cancel the water reminder" | Cancels it; it doesn't fire | |
| TEST 085 | Set a reminder 1 min away, then exit JARVIS and start it again after it was due | On startup: "while I was off you had a reminder at …" | |
| TEST 086 | Wake JARVIS in the morning | Briefing includes "You have N reminders today: …" | |
| TEST 087 | While JARVIS is answering something, let a reminder come due | Notification appears immediately; the spoken reminder follows when it's free | |
