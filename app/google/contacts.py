"""Google Contacts: turn "Rahul" into an email address."""
from __future__ import annotations


def search(service, query: str, limit: int = 5) -> list[dict]:
    people = service.people().searchContacts(
        query=query, readMask="names,emailAddresses", pageSize=limit).execute().get("results", [])
    found = []
    for result in people:
        person = result.get("person", {})
        emails = [e.get("value") for e in person.get("emailAddresses", []) if e.get("value")]
        names = [n.get("displayName") for n in person.get("names", []) if n.get("displayName")]
        if emails:
            found.append({"name": names[0] if names else emails[0], "email": emails[0]})
    return found
