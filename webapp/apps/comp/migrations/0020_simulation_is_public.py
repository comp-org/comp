# Generated by Django 2.2.6 on 2019-12-30 19:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comp', '0019_auto_20191127_1022'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulation',
            name='is_public',
            field=models.BooleanField(default=True),
        ),
    ]
