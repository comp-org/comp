# Generated by Django 3.2.8 on 2021-10-12 13:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0030_build_failed_at_stage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="build", name="provider_data", field=models.JSONField(null=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="first_name",
            field=models.CharField(
                blank=True, max_length=150, verbose_name="first name"
            ),
        ),
    ]
