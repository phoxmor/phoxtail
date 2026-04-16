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


class AbstractPhoxtailUser(
    AbstractUser,
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
):
    """Abstract base user model with Phoxtail's opinionated fields.

    Projects that need custom fields should subclass this in a local ``users``
    app and set ``AUTH_USER_MODEL`` accordingly — **before** running the first
    migration.  Otherwise the concrete ``User`` model below is used as the
    default.
    """

    email = models.EmailField(unique=True, verbose_name=_("email address"))
    born_at = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Date of birth"),
        validators=[validate_born_at],
    )
    gender = models.ForeignKey(
        "phoxtail_users.Gender",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
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
        index.AutocompleteField("get_short_id"),
        index.FilterField("is_active"),
    ]

    class Meta:
        abstract = True
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self) -> str:
        return self.get_full_name()

    @property
    def service(self):
        from phoxtail.users.services import UserService

        return UserService(self)

    @property
    def age_display(self) -> str | None:
        return get_age_display(self.born_at)


class User(AbstractPhoxtailUser):
    """Concrete default user model.

    Used when ``AUTH_USER_MODEL = "phoxtail_users.User"`` (the default for
    hatched projects).  The ``swappable`` meta option tells Django's migration
    framework to skip this table when a project points AUTH_USER_MODEL
    elsewhere.
    """

    class Meta(AbstractPhoxtailUser.Meta):
        swappable = "AUTH_USER_MODEL"


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
