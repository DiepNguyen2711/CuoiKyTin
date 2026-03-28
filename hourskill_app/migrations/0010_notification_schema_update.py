from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0009_alter_wallet_balance'),
    ]

    operations = [
        migrations.RenameField(
            model_name='notification',
            old_name='user',
            new_name='recipient',
        ),
        migrations.RenameField(
            model_name='notification',
            old_name='content',
            new_name='text',
        ),
        migrations.AddField(
            model_name='notification',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications_sent', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('comment', 'Comment'), ('follow', 'Follow'), ('rating', 'Rating')], default='comment', max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='notification',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications_received', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='notification',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
