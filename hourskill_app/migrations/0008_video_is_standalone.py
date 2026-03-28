from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hourskill_app", "0007_videoaccess_remove_video_price_tc"),
    ]

    operations = [
        migrations.AddField(
            model_name="video",
            name="is_standalone",
            field=models.BooleanField(default=False),
        ),
    ]
