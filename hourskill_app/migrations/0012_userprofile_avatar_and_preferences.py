from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0011_notification_video'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='avatar',
            field=models.ImageField(default='default.png', upload_to='avatars/'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='notify_comments',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='notify_follows',
            field=models.BooleanField(default=True),
        ),
    ]
