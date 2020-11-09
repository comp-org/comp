# Generated by Django 3.0.2 on 2020-01-11 00:22

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("comp", "0021_remove_simulation_readme")]

    operations = [
        migrations.AddField(
            model_name="simulation",
            name="readme",
            field=django.contrib.postgres.fields.jsonb.JSONField(
                blank=True, default=None, null=True
            ),
        )
    ]