from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hourskill_app", "0006_alter_category_options_remove_wallet_balance_tc_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="video",
            name="price_tc",
        ),
        migrations.CreateModel(
            name="VideoAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unlocked_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_accesses", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "video",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_records", to="hourskill_app.video"),
                ),
            ],
            options={
                "unique_together": {("user", "video")},
            },
        ),
    ]
