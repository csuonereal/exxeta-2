import uuid

from django.db import models


class PromptSession(models.Model):
    """Temporary pipeline state stored locally in SQLite (zero cloud persistence)."""

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        EXTRACTING = "Extracting", "Extracting"
        VALIDATING = "Validating", "Validating"
        CLOUD_PROCESSING = "Cloud_Processing", "Cloud Processing"
        REHYDRATING = "Rehydrating", "Rehydrating"
        COMPLETED = "Completed", "Completed"
        FAILED = "Failed", "Failed"

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_prompt = models.TextField()
    sanitized_prompt = models.TextField(blank=True, default="")
    sensitive_mapping = models.JSONField(default=dict, blank=True)
    cloud_response = models.TextField(blank=True, default="")
    final_rehydrated_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Set when status is Failed (never stores API keys).",
    )
    pipeline_logs = models.JSONField(
        default=list,
        blank=True,
        help_text="Append-only style log lines for live step-by-step UI (no API keys).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.session_id} ({self.status})"
