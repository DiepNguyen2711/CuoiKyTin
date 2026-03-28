from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0013_userprofile_specialization_bio'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='tc_added',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_vip',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='vip_expiry',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='CreatorAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('available_balance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('pending_balance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('total_earned', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='creator_account', to='hourskill_app.user')),
            ],
        ),
        migrations.CreateModel(
            name='WithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_tc', models.DecimalField(decimal_places=2, max_digits=12)),
                ('amount_vnd', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('PAID', 'Paid')], default='PENDING', max_length=12)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='withdrawal_requests', to='hourskill_app.user')),
            ],
        ),
    ]
