from django.db import migrations, models

from ribcage.identity import display_names


def fill_keys(apps, schema_editor):
    Voter = apps.get_model('identity', 'Voter')
    for voter in Voter.objects.using(schema_editor.connection.alias).all():
        voter.display_name_key = display_names.key(voter.display_name)
        voter.save(using=schema_editor.connection.alias, update_fields=['display_name_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('identity', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='voter',
            name='display_name',
            field=models.CharField(max_length=20),
        ),
        migrations.AddField(
            model_name='voter',
            name='display_name_key',
            field=models.CharField(default='', editable=False, max_length=60),
            preserve_default=False,
        ),
        # Backfill before unique, or two existing voters collide on '' (#69)
        migrations.RunPython(fill_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='voter',
            name='display_name_key',
            field=models.CharField(editable=False, max_length=60, unique=True),
        ),
    ]
