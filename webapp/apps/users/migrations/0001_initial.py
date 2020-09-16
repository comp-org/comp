# Generated by Django 2.1.7 on 2019-03-16 20:12

from django.conf import settings
import django.contrib.auth.models
import django.contrib.auth.validators
import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import webapp.apps.users.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [("auth", "0009_alter_user_last_name_max_length")]

    operations = [
        migrations.CreateModel(
            name="User",
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
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),
        migrations.CreateModel(
            name="Profile",
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
                ("is_active", models.BooleanField(default=False)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "permissions": (("access_public", "Has access to public projects"),)
            },
        ),
        migrations.CreateModel(
            name="Project",
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
                ("title", models.CharField(max_length=255)),
                ("description", models.CharField(max_length=1000)),
                ("is_public", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("live", "live"),
                            ("pending", "pending"),
                            ("requires fixes", "requires fixes"),
                        ],
                        default="live",
                        max_length=32,
                    ),
                ),
                (
                    "meta_parameters",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        blank=True, default=None, null=True
                    ),
                ),
                ("package_defaults", models.CharField(max_length=1000)),
                ("parse_user_adjustments", models.CharField(max_length=1000)),
                ("run_simulation", models.CharField(max_length=1000)),
                ("installation", models.CharField(max_length=1000)),
                (
                    "server_cost",
                    models.DecimalField(decimal_places=3, max_digits=6, null=True),
                ),
                (
                    "server_size",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=5),
                        default=webapp.apps.users.models.Project.callabledefault,
                        size=2,
                    ),
                ),
                ("exp_task_time", models.IntegerField(null=True)),
                ("exp_num_tasks", models.IntegerField(null=True)),
                (
                    "inputs_style",
                    models.CharField(
                        choices=[("paramtools", "paramtools"), ("taxcalc", "taxcalc")],
                        max_length=32,
                    ),
                ),
                (
                    "permission_type",
                    models.CharField(
                        choices=[("default", "default"), ("sponsored", "sponsored")],
                        default="default",
                        max_length=32,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projects",
                        to="users.Profile",
                    ),
                ),
                (
                    "sponsor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sponsored_projects",
                        to="users.Profile",
                    ),
                ),
            ],
        ),
    ]
