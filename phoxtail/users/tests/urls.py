"""URLConf for the profile tests: {% url %} needs the users namespace and the
account pages the profile links to, which the shared test ROOT_URLCONF does
not mount."""

from django.urls import include, path

urlpatterns = [
    path("", include("phoxtail.users.urls")),
    path("accounts/", include("allauth.urls")),
    path("core/", include("phoxtail.core.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
]
