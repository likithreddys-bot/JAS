"""Google Calendar: read meetings, create them (optionally with a Google Meet link)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta


def _when(slot: dict) -> str:
    return slot.get("dateTime") or slot.get("date", "")


def list_events(service, start: datetime, end: datetime, limit: int = 10) -> list[dict]:
    events = service.events().list(
        calendarId="primary", timeMin=start.astimezone().isoformat(), timeMax=end.astimezone().isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=limit,
    ).execute().get("items", [])
    return [{
        "id": e["id"],
        "title": e.get("summary", "(no title)"),
        "start": _when(e.get("start", {})),
        "end": _when(e.get("end", {})),
        "all_day": "date" in e.get("start", {}),
        "location": e.get("location", ""),
        "meet_link": e.get("hangoutLink", ""),
        "attendees": [a.get("email", "") for a in e.get("attendees", []) if not a.get("self")],
    } for e in events]


def describe(event: dict) -> str:
    """"Standup at 10:00 AM with rahul@example.com" for speaking aloud."""
    if event["all_day"]:
        when = "all day"
    else:
        when = f"at {datetime.fromisoformat(event['start']):%I:%M %p}".replace(" 0", " ")
    people = f" with {', '.join(a.split('@')[0] for a in event['attendees'][:3])}" if event["attendees"] else ""
    return f"{event['title']} {when}{people}"


def create_event(service, title: str, start: datetime, minutes: int, attendees: list[str],
                 add_meet: bool = True, description: str = "") -> dict:
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.astimezone().isoformat()},
        "end": {"dateTime": (start + timedelta(minutes=minutes)).astimezone().isoformat()},
        "attendees": [{"email": email} for email in attendees],
    }
    if add_meet:
        body["conferenceData"] = {"createRequest": {"requestId": uuid.uuid4().hex,
                                                    "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
    created = service.events().insert(
        calendarId="primary", body=body, conferenceDataVersion=1 if add_meet else 0,
        sendUpdates="all" if attendees else "none",
    ).execute()
    return {
        "title": created.get("summary", title),
        "start": _when(created.get("start", {})),
        "meet_link": created.get("hangoutLink", ""),
        "link": created.get("htmlLink", ""),
        "invited": [a.get("email") for a in created.get("attendees", []) if not a.get("self")],
    }
