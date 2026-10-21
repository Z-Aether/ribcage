from django.db import migrations


class Migration(migrations.Migration):
    # The hello app is gone, so its own migrations can't drop its table on the deployed database (#47, #70).

    dependencies = [
        ("identity", "0002_display_name_unique_ignoring_case"),
    ]

    operations = [
        migrations.RunSQL("DROP TABLE IF EXISTS hello_message", reverse_sql=migrations.RunSQL.noop),
    ]
