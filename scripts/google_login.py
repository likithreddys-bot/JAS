"""One-time Google sign-in for JARVIS (Calendar, Gmail, Contacts).

    .venv\\Scripts\\python.exe scripts\\google_login.py

Opens your browser, asks you to grant access, and saves the token in data/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import get_settings  # noqa: E402
from app.google.auth import build_service, load_credentials  # noqa: E402


def main() -> int:
    settings = get_settings()
    credentials = load_credentials(settings.google_client_file, settings.google_token_file, interactive=True)
    calendar = build_service("calendar", "v3", credentials)
    gmail = build_service("gmail", "v1", credentials)
    who = gmail.users().getProfile(userId="me").execute()
    calendars = calendar.calendarList().list(maxResults=5).execute().get("items", [])
    print(f"\nConnected as {who['emailAddress']}")
    print(f"Calendars: {', '.join(c.get('summary', '?') for c in calendars) or 'none'}")
    print(f"Unread emails: {who.get('messagesTotal', '?')} total in the mailbox")
    print(f"Token saved to {settings.google_token_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
