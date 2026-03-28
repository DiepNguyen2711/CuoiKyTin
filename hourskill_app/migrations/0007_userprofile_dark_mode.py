from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hourskill_app', '0006_alter_category_options_remove_wallet_balance_tc_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='dark_mode',
            field=models.BooleanField(default=False),
        ),
    ]
