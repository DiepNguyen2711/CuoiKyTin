from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hourskill_app", "0017_merge_20260328_1746"),
    ]

    operations = [
        migrations.AddField(
            model_name="video",
            name="prerequisite_video",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="dependent_videos",
                to="hourskill_app.video",
            ),
        ),
    ]
