"""Gmail: list and read messages, reply, send. Message content is untrusted data."""
from __future__ import annotations

import base64
from email.message import EmailMessage

MAX_BODY_CHARS = 4000


def _header(message: dict, name: str) -> str:
    return next((h["value"] for h in message.get("payload", {}).get("headers", []) if h["name"].lower() == name), "")


def _plain_text(payload: dict) -> str:
    if payload.get("mimeType", "").startswith("text/") and payload.get("body", {}).get("data"):
        text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
        return text if payload["mimeType"] == "text/plain" else _strip_html(text)
    for part in payload.get("parts", []):
        if found := _plain_text(part):
            return found
    return ""


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def list_messages(service, query: str = "is:unread in:inbox", limit: int = 5) -> list[dict]:
    listed = service.users().messages().list(userId="me", q=query, maxResults=limit).execute().get("messages", [])
    messages = []
    for item in listed:
        message = service.users().messages().get(
            userId="me", id=item["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]).execute()
        messages.append({
            "id": message["id"],
            "from": _header(message, "from"),
            "subject": _header(message, "subject") or "(no subject)",
            "date": _header(message, "date"),
            "snippet": message.get("snippet", ""),
            "unread": "UNREAD" in message.get("labelIds", []),
        })
    return messages


def read_message(service, message_id: str) -> dict:
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    body = _plain_text(message.get("payload", {}))
    return {
        "id": message_id,
        "thread_id": message.get("threadId"),
        "from": _header(message, "from"),
        "to": _header(message, "to"),
        "subject": _header(message, "subject") or "(no subject)",
        "date": _header(message, "date"),
        "body": body[:MAX_BODY_CHARS],
        "truncated": len(body) > MAX_BODY_CHARS,
    }


def _send(service, message: EmailMessage, thread_id: str | None = None) -> dict:
    raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    if thread_id:
        raw["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=raw).execute()
    return {"id": sent["id"], "to": message["To"], "subject": message["Subject"]}


def reply(service, message_id: str, text: str) -> dict:
    original = service.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID", "References"]).execute()
    message = EmailMessage()
    message["To"] = _header(original, "from")
    subject = _header(original, "subject")
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if reference := _header(original, "message-id"):
        message["In-Reply-To"] = reference
        message["References"] = f"{_header(original, 'references')} {reference}".strip()
    message.set_content(text)
    return _send(service, message, original.get("threadId"))


def send(service, to: str, subject: str, text: str) -> dict:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    return _send(service, message)


def mark_read(service, message_id: str) -> None:
    service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}).execute()
