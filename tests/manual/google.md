# Manual test — re-connecting Google and sharing a file

Two things landed together: the saved token had already expired ("invalid_grant: Token has been
expired or revoked" in the log), and Drive access was just added to the scopes JAS asks for. Both
need the same one action from you.

## Re-connect

```
.venv\Scripts\python.exe scripts\google_login.py
```

1. Your browser opens a Google consent screen. It will list Calendar, Gmail, Contacts **and now
   Drive** — the last one is new, and Google's own wording for it is blunt ("See, edit, create
   and delete all of your Google Drive files"). That breadth is real: `drive.file` (the narrower
   scope) cannot see files JAS did not create, and sharing an existing document needs to find it
   by name among everything already in your Drive.
2. Approve it. The script prints your email, calendars and mailbox count on success.

## Checks

| # | Say | Expect |
|---|---|---|
| 1 | "what's on my calendar today" | Reads your real meetings — confirms the token actually refreshed |
| 2 | "share the [some real file name] doc with [a contact]" | Asks first — "Should I share *name* with *email*, to view?" — before doing anything |
| 3 | Say yes | The other person gets Google's own sharing notification email, not one written by JAS |
| 4 | "share the [something that matches two files] with [someone]" | Says more than one file matches and names them, shares nothing until you're specific |
| 5 | "share the [a file name that does not exist] with [someone]" | "No file matches" — not a guess at the closest name |
| 6 | "share it so they can edit it" | The person gets edit access, not just view |

## What to check afterward

- Open the file's **Share** dialog in Drive yourself and confirm the person listed is exactly who
  you asked for, with the access level you asked for.
- JAS never reads or repeats back what is inside the file at any point in this flow — if it ever
  does, that is the rule in `JARVIS.md` §2 (item 12) being broken and worth reporting.
