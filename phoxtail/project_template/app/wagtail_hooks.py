from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from taggit.models import Tag
from wagtail.models import Locale, Site
from wagtail.snippets.models import register_snippet

User = get_user_model()


# Register additional snippets
register_snippet(Group)
register_snippet(User)
register_snippet(Site)
register_snippet(Locale)
register_snippet(Tag)
