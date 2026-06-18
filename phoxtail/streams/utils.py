def _image_url(image) -> str | None:
    """Return an absolute URL for the original image file, or None."""
    if image is None:
        return None
    try:
        url = image.file.url
    except Exception:
        return None
    if url and url.startswith("/"):
        from django.conf import settings

        base = getattr(settings, "WAGTAILADMIN_BASE_URL", "").rstrip("/")
        url = base + url
    return url or None


def _page_content_type_choices():
    """
    Callable for limit_choices_to — restricts page_types choices to
    Wagtail Page subclasses only. Called at form-render time, not import time.
    """
    try:
        from django.contrib.contenttypes.models import ContentType
        from wagtail.models import Page

        def collect_subclasses(cls):
            result = []
            for sub in cls.__subclasses__():
                result.append(sub)
                result.extend(collect_subclasses(sub))
            return result

        subclasses = [cls for cls in collect_subclasses(Page) if not cls._meta.abstract]
        if not subclasses:
            return {}
        ct_map = ContentType.objects.get_for_models(*subclasses)
        return {"pk__in": [ct.pk for ct in ct_map.values()]}
    except Exception:
        return {}
