"""Finding the menu that belongs to a request.

Lookup is exact: no falling back to another language. An absent menu means
no bar, not a bar in a language nobody asked for.
"""

from phoxtail.dashboard.models import Menu


def menu_for(site, locale):
    """The menu written for this site in this language, or None."""
    if site is None or locale is None:
        return None
    return Menu.objects.filter(site=site, locale=locale).first()


def menu_for_request(request):
    """The menu matching the request's site and the language being read."""
    from wagtail.models import Locale, Site

    site = getattr(request, "site", None) or Site.find_for_request(request)
    try:
        locale = Locale.get_active()
    except Locale.DoesNotExist:
        return None
    return menu_for(site, locale)
