"""In-memory conversation history per session_id. Ephemeral by design for this
hackathon build — history is lost on server restart. Fine for a demo; would need
a real store (DB/Redis) for anything longer-lived."""

from google.genai import types

_conversations: dict[str, list[types.Content]] = {}


def get_history(session_id: str) -> list[types.Content]:
    return _conversations.setdefault(session_id, [])
