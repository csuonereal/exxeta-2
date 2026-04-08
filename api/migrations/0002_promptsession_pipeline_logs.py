from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="promptsession",
            name="pipeline_logs",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Append-only style log lines for live step-by-step UI (no API keys).",
            ),
        ),
    ]
