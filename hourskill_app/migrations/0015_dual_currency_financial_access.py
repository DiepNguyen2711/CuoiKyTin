from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0014_financial_system_upgrade'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='balance_tc',
            field=models.DecimalField(decimal_places=2, default=Decimal('5.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='video',
            name='base_price',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='video',
            name='is_free',
            field=models.BooleanField(default=False),
        ),
        migrations.RenameField(
            model_name='creatoraccount',
            old_name='pending_balance',
            new_name='pending_vnd',
        ),
        migrations.RenameField(
            model_name='creatoraccount',
            old_name='available_balance',
            new_name='available_vnd',
        ),
        migrations.RenameField(
            model_name='creatoraccount',
            old_name='total_earned',
            new_name='total_earned_vnd',
        ),
    ]
