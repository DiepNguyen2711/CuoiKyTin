from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0010_notification_schema_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='video',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='hourskill_app.video'),
        ),
    ]
