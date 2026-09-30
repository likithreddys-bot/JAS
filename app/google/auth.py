"""One-time Google sign-in, then refreshed automatically.

The user signs in once in a browser; the resulting token is stored in data/ (never in git).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("jarvis.google")

# "Web application" OAuth clients need an exact redirect address registered in Google Cloud Console.
WEB_CLIENT_PORT = 8765
WEB_CLIENT_REDIRECT = f"http://localhost:{WEB_CLIENT_PORT}/"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # read + create meetings (incl. Google Meet links)
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.modify",  # read mail, mark as read
    "https://www.googleapis.com/auth/gmail.send",  # send only after the user confirms
    "https://www.googleapis.com/auth/contacts.readonly",  # look up "Rahul" -> email address
    # Full Drive access, not the narrower drive.file - sharing an existing document means finding
    # it by name among files JAS did not create, which drive.file cannot see at all. The file's
    # actual content is never read: share_file only ever touches metadata (name, id) and permissions.
    "https://www.googleapis.com/auth/drive",
]


class GoogleNotConnected(Exception):
    """No credentials yet: the user still has to sign in."""


def find_client_file(preferred: Path) -> tuple[Path, bool]:
    """(OAuth client JSON, is_web_client): the configured name, or any client_secret*.json Google downloaded.

    Desktop-app clients are preferred; web clients work too but need WEB_CLIENT_REDIRECT registered.
    """
    folder = preferred.parent
    candidates = [preferred, *sorted(folder.glob("client_secret*.json"))] if folder.exists() else [preferred]
    web_client = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if "installed" in data:
            return candidate, False
        if "web" in data and web_client is None:
            web_client = candidate
    if web_client is not None:
        return web_client, True
    raise GoogleNotConnected(
        f"No OAuth client file in {folder}. Download the OAuth client JSON from Google Cloud Console "
        "(Desktop app is easiest) and save it there."
    )


def load_credentials(client_file: Path, token_file: Path, interactive: bool = False):
    """Valid credentials, refreshing or (if `interactive`) asking the user to sign in."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.valid:
        return credentials
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            token_file.write_text(credentials.to_json(), encoding="utf-8")
            return credentials
        except Exception as exc:
            log.warning("Google token refresh failed: %s", exc)
    if not interactive:
        raise GoogleNotConnected(
            "Google isn't connected yet. Run: .venv\\Scripts\\python.exe scripts\\google_login.py"
        )
    client_file, is_web = find_client_file(client_file)
    log.info("Signing in with %s (%s client)", client_file.name, "web" if is_web else "desktop")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file), SCOPES, redirect_uri=WEB_CLIENT_REDIRECT if is_web else None)
    try:
        credentials = flow.run_local_server(
            port=WEB_CLIENT_PORT if is_web else 0, prompt="consent",
            authorization_prompt_message="Opening your browser to sign in to Google...")
    except Exception as exc:
        if is_web and "redirect_uri_mismatch" in str(exc).lower():
            raise GoogleNotConnected(
                f"Google rejected the sign-in address. In Google Cloud Console open this OAuth client and add "
                f"{WEB_CLIENT_REDIRECT} under 'Authorised redirect URIs' (or create a Desktop app client instead)."
            ) from exc
        raise
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    log.info("Google connected; token saved to %s", token_file)
    return credentials


def build_service(name: str, version: str, credentials):
    from googleapiclient.discovery import build

    return build(name, version, credentials=credentials, cache_discovery=False)
