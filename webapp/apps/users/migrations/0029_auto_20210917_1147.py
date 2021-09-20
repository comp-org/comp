# Generated by Django 3.0.14 on 2021-09-17 11:47

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0028_auto_20210620_1934"),
    ]

    operations = [
        migrations.CreateModel(
            name="Build",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("cluster_build_id", models.IntegerField(null=True)),
                ("created_at", models.DateTimeField(null=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("cancelled_at", models.DateTimeField(null=True)),
                (
                    "provider_data",
                    django.contrib.postgres.fields.jsonb.JSONField(null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("building", "Building"),
                            ("testing", "Testing"),
                            ("pushing", "Pushing"),
                            ("cancelled", "Cancelled"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                (
                    "cluster",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="builds",
                        to="users.Cluster",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="builds",
                        to="users.Project",
                    ),
                ),
                (
                    "tag",
                    models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="build",
                        to="users.Tag",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="build",
            constraint=models.UniqueConstraint(
                fields=("cluster", "cluster_build_id"), name="unique_cluster_build"
            ),
        ),
    ]
