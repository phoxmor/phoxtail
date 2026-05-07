from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase
from wagtail.admin.panels import (
    FieldPanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
    TitleFieldPanel,
)
from wagtail.models import Page
from wagtail.search import index
from wagtail.search.backends import get_search_backend
from wagtail.snippets.models import register_snippet

from phoxtail.blog.streams import BlogIndexBodyStreamField, BlogPostBodyStreamField
from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin
from phoxtail.core.utils import paginate_queryset

User = get_user_model()


@register_snippet
class BlogAuthor(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="blog_author",
    )
    title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Title"),
        help_text=_("Author's role or position, e.g. 'Software Engineer' or 'Editor'."),
    )
    bio = models.TextField(
        blank=True,
        verbose_name=_("Bio"),
        help_text=_("Short biography of the author."),
    )

    panels = [
        FieldPanel("user"),
        FieldPanel("title"),
        FieldPanel("bio"),
    ]

    search_fields = [
        index.RelatedFields(
            "user",
            [
                index.AutocompleteField("first_name"),
                index.AutocompleteField("last_name"),
                index.AutocompleteField("email"),
            ],
        ),
        index.SearchField("title"),
        index.SearchField("bio"),
    ]

    class Meta:
        verbose_name = _("Blog Author")
        verbose_name_plural = _("Blog Authors")

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class BlogIndexPage(Page):
    subpage_types = ["phoxtail_blog.BlogPostPage"]
    template = "phoxtail_blog/list/index.html"

    body = BlogIndexBodyStreamField

    posts_per_page = models.PositiveIntegerField(
        default=10, help_text=_("How many blog posts to display per page")
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
        FieldPanel("posts_per_page"),
    ]
    promote_panels = [
        MultiFieldPanel(
            [
                FieldPanel("slug"),
                FieldPanel("seo_title"),
                FieldPanel("search_description"),
            ],
            heading=_("For search engines"),
        ),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        blog_posts = BlogPostPage.objects.live().child_of(self)

        search_query = request.GET.get("q", "")
        if search_query:
            backend = get_search_backend()
            blog_posts = backend.autocomplete(search_query, blog_posts)

        paginator, search_query = paginate_queryset(
            blog_posts, request, search_query, objects_per_page=self.posts_per_page
        )

        context["paginator"] = paginator
        context["search_query"] = search_query

        return context

    def serve(self, request, *args, **kwargs):
        context = self.get_context(request, *args, **kwargs)
        return render(request, self.template, context)

    class Meta:
        verbose_name = _("Blog")
        verbose_name_plural = _("Blog")


class BlogPostPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "BlogPostPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class BlogPostPage(TimestampMixin, Page):
    template = "phoxtail_blog/detail/object.html"
    parent_page_types = ["phoxtail_blog.BlogIndexPage"]

    preview_image = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=_("Featured image for this post"),
    )

    tags = ClusterTaggableManager(
        through=BlogPostPageTag,
        blank=True,
        help_text=_("Tags for categorizing blog posts"),
    )

    intro = models.TextField(
        null=True,
        blank=True,
        help_text=_("Brief introduction or summary of the post"),
    )

    read_mins = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Estimated reading time in minutes"),
        verbose_name=_("Reading Time"),
        validators=[
            MinValueValidator(1, _("Reading time must be at least 1 minute")),
        ],
    )

    body = BlogPostBodyStreamField

    author = models.ForeignKey(
        "phoxtail_blog.BlogAuthor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blog_posts",
        help_text=_("The author of this post"),
    )

    first_published_at_override = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Published Date Override"),
        help_text=_(
            "Overrides the system-managed first published date."
            " Use when the original publication date differs"
            " from when the page was first created in the CMS."
        ),
    )
    last_published_at_override = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Updated Date Override"),
        help_text=_(
            "Overrides the system-managed last published date."
            " Set only for significant updates"
            " — not minor corrections."
        ),
    )
    hide_dates = models.BooleanField(
        default=False,
        verbose_name=_("Hide Dates"),
        help_text=_(
            "If checked, no publication or update dates will be shown on this post."
        ),
    )

    content_panels = [
        TitleFieldPanel("title"),
        FieldPanel("body"),
    ]

    details_panels = [
        FieldPanel("author"),
        FieldPanel("intro"),
        FieldPanel("read_mins"),
        FieldPanel("preview_image"),
        FieldPanel("tags"),
    ]

    publishing_panels = [
        FieldPanel("hide_dates"),
        FieldPanel("first_published_at_override"),
        FieldPanel("last_published_at_override"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(content_panels, heading=_("Content")),
            ObjectList(details_panels, heading=_("Details")),
            ObjectList(publishing_panels, heading=_("Publishing")),
            ObjectList(
                [
                    MultiFieldPanel(
                        [
                            FieldPanel("slug"),
                            FieldPanel("seo_title"),
                            FieldPanel("search_description"),
                        ],
                        heading=_("For search engines"),
                    ),
                ],
                heading=_("Promote"),
            ),
            ObjectList(Page.settings_panels, heading=_("Settings")),
        ]
    )

    search_fields = Page.search_fields + [index.AutocompleteField("intro")]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        related_posts = (
            BlogPostPage.objects.live()
            .child_of(self.get_parent())
            .exclude(id=self.id)
            .distinct()
        )
        context["related_posts"] = related_posts[:3]

        return context

    class Meta:
        verbose_name = _("Blog Post")
        verbose_name_plural = _("Blog Posts")
