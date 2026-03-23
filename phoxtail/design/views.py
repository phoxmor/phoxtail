from wagtail.admin.ui.tables import Column, TitleColumn
from wagtail.snippets.views.chooser import (
    ChooseResultsView,
    ChooseView,
)
from wagtail.snippets.views.chooser import (
    SnippetChooserViewSet as BaseSnippetChooserViewSet,
)

from .models import Palette


class PaletteChooseView(ChooseView):
    @property
    def title_column(self):
        return TitleColumn(
            "title",
            label="Palette Name",
            accessor="title",
            id_accessor="pk",
            url_name=self.chosen_url_name,
            link_attrs={"data-chooser-modal-choice": True},
        )

    @property
    def columns(self):
        columns = super().columns
        columns.append(
            Column(
                "shades_preview",
                label="Shades",
                accessor=lambda obj: obj.shades_preview(),
            )
        )
        return columns


class PaletteChooseResultsView(ChooseResultsView):
    @property
    def title_column(self):
        return TitleColumn(
            "title",
            label="Palette Name",
            accessor="title",
            id_accessor="pk",
            url_name=self.chosen_url_name,
            link_attrs={"data-chooser-modal-choice": True},
        )

    @property
    def columns(self):
        columns = super().columns
        columns.append(
            Column(
                "shades_preview",
                label="Shades",
                accessor=lambda obj: obj.shades_preview(),
            )
        )
        return columns


class PaletteChooserViewSet(BaseSnippetChooserViewSet):
    model = Palette
    choose_view_class = PaletteChooseView
    choose_results_view_class = PaletteChooseResultsView
