# Generated by Django 2.1.5 on 2019-02-22 19:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("users", "0005_project_installation")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="description",
            field=models.CharField(default="", max_length=1000),
            preserve_default=False,
        )
    ]