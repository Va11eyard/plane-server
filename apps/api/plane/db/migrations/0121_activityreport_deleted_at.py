# Generated migration to add missing deleted_at field to ActivityReport

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0120_activityreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="activityreport",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
        ),
    ]
