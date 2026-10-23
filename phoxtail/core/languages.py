from django.conf import settings
from django.urls import translate_url
from django.utils.translation import get_language, get_language_info


def languages(request):
    """The languages a page can be read in, each with this page's URL in it.

    Every language the project serves. A page that is not a Wagtail page has
    no ``get_translations`` to walk, so its path is re-prefixed with
    ``translate_url`` instead. Empty without a second language: there is
    nothing to switch to.
    """
    # Without i18n there are no language prefixes to move between, and
    # set_language is not published either.
    served = getattr(settings, "LANGUAGES", []) if settings.USE_I18N else []
    if len(served) < 2:
        return []

    path = request.get_full_path() if request else "/"
    active = get_language()

    options = []
    for code, _label in served:
        info = get_language_info(code)
        options.append(
            {
                "code": code,
                "name": info["name"],
                "name_local": info["name_local"],
                "url": translate_url(path, code),
                "active": code == active,
            }
        )
    return options
