from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hourskill_app", "0019_course_category_text_alter_course_category"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="course",
            name="bundle_price_tc",
        ),
    ]
