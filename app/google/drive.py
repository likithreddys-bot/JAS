"""Google Drive: find a file by name and share it - metadata and permissions only.

`find` never asks for a file's content, only `fields=... name, modifiedTime, webViewLink` - the
search itself cannot read what is inside a document. See CLAUDE.md §2 rule 12.
"""
from __future__ import annotations


def find(service, name: str, limit: int = 5) -> list[dict]:
    """Files whose name contains `name`, most recently modified first. Metadata only."""
    escaped = name.replace("'", "\\'")
    result = service.files().list(
        q=f"name contains '{escaped}' and trashed = false",
        fields="files(id, name, modifiedTime, webViewLink, mimeType)",
        orderBy="modifiedTime desc",
        pageSize=limit,
    ).execute()
    return [{"id": f["id"], "name": f["name"], "modified": f["modifiedTime"], "link": f["webViewLink"]}
            for f in result.get("files", [])]


def share(service, file_id: str, email: str, role: str = "reader", message: str = "") -> dict:
    """Grants access and lets Google send the person its own notification email."""
    service.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": role, "emailAddress": email},
        sendNotificationEmail=True,
        emailMessage=message or None,
        fields="id",
    ).execute()
    return {"shared_with": email, "role": role}
