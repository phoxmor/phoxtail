from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from sorl.thumbnail import ImageField
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

from .managers import UserManager
from .utils import get_age_display
from .validators import validate_born_at


class User(
    AbstractUser,
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
):
    email = models.EmailField(unique=True, verbose_name=_("email address"))
    born_at = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Date of birth"),
        validators=[validate_born_at],
    )
    gender = models.ForeignKey(
        "users.Gender", blank=True, null=True, on_delete=models.SET_NULL
    )
    country = CountryField(blank=True, null=True)

    phone_number = PhoneNumberField(blank=True, null=True)
    avatar = ImageField(upload_to="avatars/", blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    search_fields = [
        index.AutocompleteField("email"),
        index.AutocompleteField("username"),
        index.AutocompleteField("first_name"),
        index.AutocompleteField("last_name"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self) -> str:
        return self.get_full_name()

    @property
    def age_display(self) -> str | None:
        return get_age_display(self.born_at)


@register_snippet
class Gender(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(
        max_length=10,
        unique=True,
        null=True,
        blank=True,
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("symbol"),
    ]

    class Meta:
        verbose_name = _("Gender")
        verbose_name_plural = _("Genders")
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["symbol"]),
        ]

    def __str__(self):
        return self.name
