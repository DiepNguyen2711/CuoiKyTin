from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0012_userprofile_avatar_and_preferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='specialization',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='bio',
            field=models.TextField(blank=True, default=''),
        ),
    ]
