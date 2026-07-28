from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import InferenceProvider, ModelArtifact


class InferenceProviderViewSet(SnippetViewSet):
    model = InferenceProvider
    icon = "hub"
    menu_label = _("Providers")
    menu_name = _("Providers")
    menu_order = 100
    list_display = [
        "display_name",
        "model_prefix",
        "base_url",
        "api_key_env_var",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["display_name", "identifier", "base_url"]

    panels = [
        FieldPanel("identifier"),
        FieldPanel("display_name"),
        FieldPanel("model_prefix"),
        FieldPanel("base_url"),
        FieldPanel("api_key_env_var"),
        FieldPanel("is_active"),
    ]


class ModelArtifactViewSet(SnippetViewSet):
    model = ModelArtifact
    icon = "cognition-2"
    menu_label = _("Models")
    menu_name = _("Models")
    menu_order = 200
    list_display = [
        "display_name",
        "provider",
        "identifier",
        "permission",
        "is_active",
        "sort_order",
    ]
    list_filter = ["provider", "is_active"]
    search_fields = ["display_name", "identifier"]

    panels = [
        FieldPanel("provider"),
        FieldPanel("identifier"),
        FieldPanel("display_name"),
        FieldPanel("permission"),
        FieldPanel("is_active"),
    ]
