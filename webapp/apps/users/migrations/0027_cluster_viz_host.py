# Generated by Django 3.0.14 on 2021-04-11 20:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0026_tag_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="cluster",
            name="viz_host",
            field=models.CharField(max_length=128, null=True),
        ),
    ]