from phoxtail.streams.fields import SchemaStreamField


def get_blog_post_body_blocks():
    from django.contrib.contenttypes.models import ContentType
    from django.db import OperationalError, ProgrammingError

    from phoxtail.blog.models import BlogPostPage
    from phoxtail.streams.cache import get_cached_blocks_for_page_type

    try:
        ct = ContentType.objects.get_for_model(BlogPostPage)
        return get_cached_blocks_for_page_type(ct.id)
    except (ProgrammingError, OperationalError):
        return []


BlogPostBodyStreamField = SchemaStreamField(
    get_blog_post_body_blocks,
    null=True,
    blank=True,
    collapsed=True,
)


def get_blog_index_body_blocks():
    from django.contrib.contenttypes.models import ContentType
    from django.db import OperationalError, ProgrammingError

    from phoxtail.blog.models import BlogIndexPage
    from phoxtail.streams.cache import get_cached_blocks_for_page_type

    try:
        ct = ContentType.objects.get_for_model(BlogIndexPage)
        return get_cached_blocks_for_page_type(ct.id)
    except (ProgrammingError, OperationalError):
        return []


BlogIndexBodyStreamField = SchemaStreamField(
    get_blog_index_body_blocks,
    null=True,
    blank=True,
    collapsed=True,
)
