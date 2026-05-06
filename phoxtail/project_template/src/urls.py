from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from phoxtail.core.wiring import collect_url_patterns
from phoxtail.users.views import redirect_to_allauth_login

urlpatterns = [
    path("admin/login/", redirect_to_allauth_login),
    path("admin/", include(wagtailadmin_urls)),
    path("django-admin/", admin.site.urls),
    path("documents/", include(wagtaildocs_urls)),
    path("api/", include("phoxtail.api.urls")),
    path("phoxtail_core/", include("phoxtail.core.urls")),
    path("users/", include("phoxtail.users.urls")),
]

urlpatterns += collect_url_patterns()

# Development
if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]

# Wagtail — i18n catch-all at the bottom
urlpatterns += i18n_patterns(
    path("accounts/", include("allauth.urls")),
    path("", include(wagtail_urls)),
)
