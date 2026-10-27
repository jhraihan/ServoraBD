from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable",
                 database=schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
