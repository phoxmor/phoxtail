# Generated manually for phoxtail.users library app

import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
import django_countries.fields
import modelsearch.index
import phonenumber_field.modelfields
import phoxtail.core.mixins
import phoxtail.users.managers
import phoxtail.users.validators
import sorl.thumbnail.fields
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Gender",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=50, unique=True)),
                (
                    "symbol",
                    models.CharField(
                        blank=True, max_length=10, null=True, unique=True
                    ),
                ),
            ],
            options={
                "verbose_name": "Gender",
                "verbose_name_plural": "Genders",
            },
            bases=(
                models.Model,
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
            ),
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
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
                        help_text=(
                            "Designates that this user has all permissions"
                            " without explicitly assigning them."
                        ),
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text=(
                            "Required. 150 characters or fewer."
                            " Letters, digits and @/./+/-/_ only."
                        ),
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
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Designates whether the user can log into"
                            " this admin site."
                        ),
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Designates whether this user should be"
                            " treated as active. Unselect this instead"
                            " of deleting accounts."
                        ),
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="date joined",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "email",
                    models.EmailField(
                        max_length=254,
                        unique=True,
                        verbose_name="email address",
                    ),
                ),
                (
                    "born_at",
                    models.DateField(
                        blank=True,
                        null=True,
                        validators=[phoxtail.users.validators.validate_born_at],
                        verbose_name="Date of birth",
                    ),
                ),
                (
                    "country",
                    django_countries.fields.CountryField(
                        blank=True, max_length=2, null=True
                    ),
                ),
                (
                    "phone_number",
                    phonenumber_field.modelfields.PhoneNumberField(
                        blank=True, max_length=128, null=True, region=None
                    ),
                ),
                (
                    "avatar",
                    sorl.thumbnail.fields.ImageField(
                        blank=True, null=True, upload_to="avatars/"
                    ),
                ),
                (
                    "gender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="phoxtail_users.gender",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "The groups this user belongs to. A user will"
                            " get all permissions granted to each of"
                            " their groups."
                        ),
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
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
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "abstract": False,
                "swappable": "AUTH_USER_MODEL",
            },
            bases=(
                models.Model,
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
            ),
            managers=[
                ("objects", phoxtail.users.managers.UserManager()),
            ],
        ),
        migrations.AddIndex(
            model_name="gender",
            index=models.Index(
                fields=["name"],
                name="phoxtail_us_name_47db40_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="gender",
            index=models.Index(
                fields=["symbol"],
                name="phoxtail_us_symbol_046c6b_idx",
            ),
        ),
    ]
