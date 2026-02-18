# Migration to add missing deleted_at field to ActivityReport (idempotent)

from django.db import migrations, models


def add_deleted_at_if_not_exists(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'activity_reports' AND column_name = 'deleted_at'
            """
        )
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE activity_reports ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE NULL"
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0120_activityreport"),
    ]

    operations = [
        migrations.RunPython(add_deleted_at_if_not_exists, noop),
        migrations.AlterField(
            model_name="activityreport",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
        ),
    ]
