# Generated by Django 2.1.5 on 2019-02-22 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("users", "0006_project_description")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("live", "live"),
                    ("pending", "pending"),
                    ("requires fixes", "requires fixes"),
                ],
                default="live",
                max_length=32,
            ),
        )
    ]