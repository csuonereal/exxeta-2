import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PromptSession",
            fields=[
                (
                    "session_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("raw_prompt", models.TextField()),
                ("sanitized_prompt", models.TextField(blank=True, default="")),
                ("sensitive_mapping", models.JSONField(blank=True, default=dict)),
                ("cloud_response", models.TextField(blank=True, default="")),
                ("final_rehydrated_text", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("Pending", "Pending"),
                            ("Extracting", "Extracting"),
                            ("Validating", "Validating"),
                            ("Cloud_Processing", "Cloud Processing"),
                            ("Rehydrating", "Rehydrating"),
                            ("Completed", "Completed"),
                            ("Failed", "Failed"),
                        ],
                        db_index=True,
                        default="Pending",
                        max_length=32,
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Set when status is Failed (never stores API keys).",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
