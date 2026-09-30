import base64
from datetime import datetime

import pytest

from app.google import calendar, gmail
from app.google.auth import GoogleNotConnected
from app.tools.base import Risk
from app.tools.google_tools import GoogleServices, _day_range, google_tools

NOW = datetime(2026, 9, 22, 17, 0)  # Tuesday 5 PM


class FakeCalendar:
    def __init__(self):
        self.created = None

    def events(self):
        return self

    def list(self, **kwargs):
        self.listed = kwargs
        return self

    def insert(self, **kwargs):
        self.created = kwargs
        body = kwargs["body"]
        return _Returns({"summary": body["summary"], "start": body["start"], "htmlLink": "https://cal/x",
                         "hangoutLink": "https://meet.google.com/abc-defg" if "conferenceData" in body else "",
                         "attendees": body["attendees"] + [{"email": "me@example.com", "self": True}]})

    def execute(self):
        return {"items": [
            {"id": "1", "summary": "Standup", "start": {"dateTime": "2026-09-22T10:00:00+05:30"},
             "end": {"dateTime": "2026-09-22T10:15:00+05:30"},
             "attendees": [{"email": "rahul@example.com"}, {"email": "me@example.com", "self": True}]},
            {"id": "2", "summary": "Design review", "start": {"dateTime": "2026-09-22T15:30:00+05:30"},
             "end": {"dateTime": "2026-09-22T16:30:00+05:30"}, "hangoutLink": "https://meet.google.com/xyz"},
        ]}


class _Returns:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeGmail:
    def __init__(self):
        self.sent = None

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kwargs):
        self.query = kwargs
        return _Returns({"messages": [{"id": "m1"}]})

    def get(self, **kwargs):
        if kwargs.get("format") == "full":
            body = base64.urlsafe_b64encode(b"Hi Alex,\n\nCan we move the meeting?\n").decode()
            return _Returns({"id": "m1", "threadId": "t1", "payload": {
                "headers": [{"name": "From", "value": "Rahul <rahul@example.com>"},
                            {"name": "Subject", "value": "Meeting"}, {"name": "Message-ID", "value": "<abc@mail>"}],
                "mimeType": "text/plain", "body": {"data": body}}})
        return _Returns({"id": "m1", "threadId": "t1", "labelIds": ["UNREAD"], "snippet": "Can we move...",
                         "payload": {"headers": [{"name": "From", "value": "Rahul <rahul@example.com>"},
                                                 {"name": "Subject", "value": "Meeting"},
                                                 {"name": "Message-ID", "value": "<abc@mail>"},
                                                 {"name": "Date", "value": "Tue, 22 Sep 2026 09:00:00 +0530"}]}})

    def send(self, **kwargs):
        self.sent = kwargs["body"]
        return _Returns({"id": "sent1"})


class FakePeople:
    def people(self):
        return self

    def searchContacts(self, **kwargs):
        self.query = kwargs["query"]
        if "rahul" not in kwargs["query"].lower():
            return _Returns({"results": []})
        return _Returns({"results": [{"person": {"names": [{"displayName": "Rahul Sharma"}],
                                                 "emailAddresses": [{"value": "rahul@example.com"}]}}]})


class FakeDrive:
    """Files that exist in a fake Drive - "Budget.xlsx" matches once, "Report" matches twice."""

    def __init__(self):
        self.list_call = None
        self.shared = None

    def files(self):
        return self

    CATALOGUE = [
        {"id": "f1", "name": "Budget.xlsx", "modifiedTime": "2026-09-20T10:00:00Z",
         "webViewLink": "https://drive/f1", "mimeType": "x"},
        {"id": "f2", "name": "Report Draft.docx", "modifiedTime": "2026-09-21T10:00:00Z",
         "webViewLink": "https://drive/f2", "mimeType": "x"},
        {"id": "f3", "name": "Report Final.docx", "modifiedTime": "2026-09-22T10:00:00Z",
         "webViewLink": "https://drive/f3", "mimeType": "x"},
    ]

    def list(self, **kwargs):
        self.list_call = kwargs
        # Pull the searched term straight out of "name contains 'term' and trashed = false",
        # exactly what app/google/drive.py builds, rather than re-parsing Drive query syntax.
        term = kwargs["q"].split("'")[1].lower()
        return _Returns({"files": [f for f in self.CATALOGUE if term in f["name"].lower()]})

    def permissions(self):
        return self

    def create(self, **kwargs):
        self.shared = kwargs
        return _Returns({"id": "perm1"})


@pytest.fixture
def tools():
    fakes = {"calendar": FakeCalendar(), "gmail": FakeGmail(), "people": FakePeople(), "drive": FakeDrive()}
    services = GoogleServices(lambda: object())
    services._services = fakes
    return {t.name: t for t in google_tools(services, now=lambda: NOW)}, fakes


@pytest.mark.parametrize("day, starts, ends", [
    ("today", NOW, datetime(2026, 9, 22, 23, 59, 59, 999999)),
    ("tomorrow", datetime(2026, 9, 23, 0, 0), datetime(2026, 9, 23, 23, 59, 59, 999999)),
])
def test_day_ranges(day, starts, ends):
    start, end, _ = _day_range(day, NOW)
    assert start == starts and end == ends


def test_meetings_are_listed_and_described(tools):
    tool, _ = tools
    result = tool["list_meetings"].run(day="today")
    assert result.ok and result.data["count"] == 2
    assert result.data["summary"] == "Standup at 10:00 AM with rahul; Design review at 3:30 PM"


def test_meeting_is_created_with_meet_link_and_contact_lookup(tools):
    tool, fakes = tools
    result = tool["create_meeting"].run(title="Sync", at="2026-09-23T15:00", attendees="Rahul", minutes=45)
    assert result.ok and result.data["meet_link"].startswith("https://meet.google.com/")
    body = fakes["calendar"].created["body"]
    assert body["attendees"] == [{"email": "rahul@example.com"}]
    assert body["start"]["dateTime"].startswith("2026-09-23T15:00") and body["end"]["dateTime"].startswith("2026-09-23T15:45")
    assert tool["create_meeting"].risk_for({"title": "Sync", "at": "2026-09-23T15:00"}) is Risk.MEDIUM


def test_unknown_attendee_is_reported_not_guessed(tools):
    tool, _ = tools
    result = tool["create_meeting"].run(title="Sync", at="2026-09-23T15:00", attendees="Batman")
    assert not result.ok and "couldn't find an email address for Batman" in result.error


def test_email_is_listed_read_and_replied_in_thread(tools):
    tool, fakes = tools
    listed = tool["list_emails"].run()
    assert listed.data["emails"][0]["subject"] == "Meeting" and listed.data["emails"][0]["unread"]
    read = tool["read_email"].run(email_id="m1")
    assert "Can we move the meeting?" in read.data["body"] and "not instructions" in read.data["note"]

    reply = tool["reply_to_email"]
    assert reply.risk_for({"email_id": "m1", "text": "Sure"}) is Risk.MEDIUM
    assert "Sure, 4 PM works" in reply.confirm_question(email_id="m1", text="Sure, 4 PM works for me.")
    assert reply.run(email_id="m1", text="Sure, 4 PM works for me.").ok
    sent = base64.urlsafe_b64decode(fakes["gmail"].sent["raw"]).decode()
    assert fakes["gmail"].sent["threadId"] == "t1"
    assert "To: Rahul <rahul@example.com>" in sent and "Subject: Re: Meeting" in sent
    assert "In-Reply-To: <abc@mail>" in sent and "Sure, 4 PM works for me." in sent


def test_a_file_is_shared_by_name_and_google_sends_the_notification(tools):
    tool, fakes = tools
    result = tool["share_file"].run(name="Budget", share_with="rahul@example.com", message="here you go")
    assert result.ok
    assert result.data == {"shared_with": "rahul@example.com", "role": "reader", "file": "Budget.xlsx"}
    body = fakes["drive"].shared
    assert body["fileId"] == "f1"
    assert body["body"] == {"type": "user", "role": "reader", "emailAddress": "rahul@example.com"}
    assert body["sendNotificationEmail"] is True and body["emailMessage"] == "here you go"


def test_share_with_a_contact_name_resolves_the_address_first(tools):
    tool, fakes = tools
    result = tool["share_file"].run(name="Budget", share_with="Rahul")
    assert result.ok and result.data["shared_with"] == "rahul@example.com"


def test_editing_access_can_be_asked_for(tools):
    tool, fakes = tools
    tool["share_file"].run(name="Budget", share_with="rahul@example.com", role="writer")
    assert fakes["drive"].shared["body"]["role"] == "writer"


def test_no_matching_file_is_a_clear_error_not_a_guess(tools):
    tool, _ = tools
    result = tool["share_file"].run(name="Nonexistent Thing", share_with="rahul@example.com")
    assert not result.ok and "No file matches" in result.error


def test_more_than_one_match_asks_rather_than_picking_one(tools):
    """Sharing the wrong document with an outside person is a real mistake - guessing is not
    acceptable here even though it might be fine for, say, opening an app."""
    tool, fakes = tools
    result = tool["share_file"].run(name="Report", share_with="rahul@example.com")
    assert not result.ok
    assert "Report Draft.docx" in result.error and "Report Final.docx" in result.error
    assert fakes["drive"].shared is None, "nothing must be shared while it is still ambiguous"


def test_unknown_person_to_share_with_is_reported_not_guessed(tools):
    tool, _ = tools
    result = tool["share_file"].run(name="Budget", share_with="Batman")
    assert not result.ok and "No contact matches" in result.error


def test_sharing_asks_for_confirmation_and_never_reads_the_files_content(tools):
    tool, fakes = tools
    share = tool["share_file"]
    assert share.risk_for({"name": "Budget", "share_with": "rahul@example.com"}) is Risk.MEDIUM
    question = share.confirm_question(name="Budget", share_with="rahul@example.com")
    assert "Budget" in question and "rahul@example.com" in question

    share.run(name="Budget", share_with="rahul@example.com")
    assert fakes["drive"].list_call["fields"] == "files(id, name, modifiedTime, webViewLink, mimeType)", \
        "the search must ask for metadata only, never a field that would return the file's content"


def test_tools_explain_when_google_is_not_connected():
    def not_connected():
        raise GoogleNotConnected("Google isn't connected yet. Run: scripts\\google_login.py")

    services = GoogleServices(not_connected)
    tool = {t.name: t for t in google_tools(services)}["list_meetings"]
    assert services.connected is False
    result = tool.run(day="today")
    assert not result.ok and "isn't connected" in result.error


def test_plain_text_is_extracted_from_html_only_mail():
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(
            b"<html><style>p{}</style><p>Hello <b>Alex</b></p></html>").decode()}}]}
    assert gmail._plain_text(payload) == "Hello Alex"


def test_briefing_reads_meetings_when_connected(tmp_path, monkeypatch):
    from app.memory.store import MemoryStore
    from app.routines import briefing
    from app.tools import weather

    monkeypatch.setattr(weather, "today", lambda city: (_ for _ in ()).throw(OSError()))
    text = briefing.build_briefing("Alex", "London", MemoryStore(tmp_path / "m.db"), lambda: [],
                                   meetings=lambda: ["Standup at 10:00", "Design review at 15:30"], now=lambda: NOW)
    assert "You have 2 meetings today: Standup at 10:00 and Design review at 15:30." in text
    assert "can't see your meetings" not in text


def test_all_day_events_are_described_without_a_time():
    event = {"title": "Holiday", "start": "2026-09-22", "all_day": True, "attendees": []}
    assert calendar.describe(event) == "Holiday all day"


def test_client_file_is_found_by_any_name_and_web_clients_are_rejected(tmp_path):
    import json

    from app.google.auth import find_client_file

    preferred = tmp_path / "google_client.json"
    with pytest.raises(GoogleNotConnected, match="No OAuth client file"):
        find_client_file(preferred)

    web = tmp_path / "client_secret_123.apps.googleusercontent.com.json"
    web.write_text(json.dumps({"web": {"client_id": "x"}}), encoding="utf-8")
    assert find_client_file(preferred) == (web, True)  # usable, but needs the redirect address registered

    desktop = tmp_path / "client_secret_456.apps.googleusercontent.com.json"
    desktop.write_text(json.dumps({"installed": {"client_id": "x"}}), encoding="utf-8")
    assert find_client_file(preferred) == (desktop, False)  # desktop clients win
    preferred.write_text(json.dumps({"installed": {"client_id": "y"}}), encoding="utf-8")
    assert find_client_file(preferred) == (preferred, False)  # the configured name wins
