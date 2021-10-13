# Generated by Django 2.2.1 on 2019-08-05 21:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("comp", "0013_inputs_client")]

    operations = [
        migrations.AlterField(
            model_name="inputs",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("SUCCESS", "Success"),
                    ("INVALID", "Invalid"),
                    ("FAIL", "Fail"),
                    ("WORKER_FAILURE", "Worker Failure"),
                ],
                max_length=20,
            ),
        )
    ]