from django import template

register = template.Library()


@register.simple_tag
def get_recent_blog_posts(blog_index_page, count=3):
    if not blog_index_page:
        return []
    from phoxtail.blog.models import BlogPostPage

    return (
        BlogPostPage.objects.live()
        .child_of(blog_index_page)
        .order_by("-first_published_at")[:count]
    )
