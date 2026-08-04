"""Optional Jira Cloud filing for in-app feedback.

Design notes:
- Feedback ALWAYS saves to our own `feedback` table and ALWAYS alerts admins
  by email regardless of Jira — this module only adds a Jira issue on top
  when settings.jira_configured is True. If Jira isn't set up yet (free
  Jira Cloud account, up to 10 users, no cost — see app.config for the
  token URL), create_issue() returns None and the caller stores the error
  on the feedback row without failing the request.
- Uses httpx.AsyncClient, matching the existing pattern in ai_service.py
  for external HTTP calls (Ollama). No new dependency — httpx is already
  a project dependency.
- Auth: HTTP Basic with base64(email:api_token), per Jira Cloud REST API v3.
"""
import base64
import logging
import httpx
from app.config import settings

log = logging.getLogger("fluidgo.jira")

CATEGORY_LABELS = {
    "bug": "fluidgo-bug",
    "idea": "fluidgo-idea",
    "question": "fluidgo-question",
    "other": "fluidgo-feedback",
}


def _adf_description(text: str) -> dict:
    """Wrap plain text in the minimal Atlassian Document Format Jira v3
    requires for the `description` field."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def create_issue(summary: str, description: str, reporter_email: str, category: str) -> dict | None:
    """Files a Jira issue. Returns {"key": "FGO-42", "url": "..."} on success,
    or None if Jira isn't configured or the call fails (never raises — the
    feedback flow must not break because Jira is down or misconfigured)."""
    if not settings.jira_configured:
        return None

    auth = base64.b64encode(f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}".encode()).decode()
    label = CATEGORY_LABELS.get(category, "fluidgo-feedback")
    payload = {
        "fields": {
            "project": {"key": settings.JIRA_PROJECT_KEY},
            "summary": summary[:255],
            "description": _adf_description(f"{description}\n\nReported by: {reporter_email}"),
            "issuetype": {"name": settings.JIRA_ISSUE_TYPE},
            "labels": [label],
        }
    }
    url = f"{settings.JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        if resp.status_code not in (200, 201):
            log.error("Jira issue creation failed (%s): %s", resp.status_code, resp.text[:500])
            return None
        data = resp.json()
        key = data.get("key")
        if not key:
            return None
        issue_url = f"{settings.JIRA_BASE_URL.rstrip('/')}/browse/{key}"
        return {"key": key, "url": issue_url}
    except Exception as e:
        log.error("Jira issue creation raised: %s", e)
        return None
