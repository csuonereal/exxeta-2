"""Helpers for prompt session lifecycle (privacy / zero-trace)."""

from __future__ import annotations

import uuid

from django.db import transaction

from .models import PromptSession


def delete_prompt_session(session_id: uuid.UUID | str) -> bool:
    """
    Permanently remove a session row from the local database.

    Returns True if a row was deleted, False if no matching session existed.
    """
    if isinstance(session_id, str):
        session_id = uuid.UUID(session_id)
    with transaction.atomic():
        deleted, _ = PromptSession.objects.filter(pk=session_id).delete()
    return deleted > 0
