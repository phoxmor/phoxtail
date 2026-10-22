from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from phoxtail.core.fields import SingleSelectSearchField
from phoxtail.remotes.models import Remote


class RemoteSelectForm(forms.Form):
    remote = SingleSelectSearchField(
        queryset=Remote.objects.all(),
        required=False,
        label=_("Remote"),
    )


class SyncModeForm(forms.Form):
    mode = forms.ChoiceField(
        choices=[
            ("remote", pgettext_lazy("sync mode", "Remote")),
            ("local", pgettext_lazy("sync mode", "Local")),
        ],
        widget=forms.RadioSelect,
        label="",
    )


class SyncSearchForm(forms.Form):
    """The list's search and page, prefixed so neither meets the Wagtail admin's own names."""

    search = forms.CharField(label=_("Search"), required=False)
    page = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)


DEVICES = {"desktop": _("Desktop"), "tablet": _("Tablet"), "mobile": _("Mobile")}


class PreviewForm(forms.Form):
    """Which preview a variant's drawer shows: a device it has a picture for, and a theme."""

    device = forms.ChoiceField(label=_("Device"), widget=forms.RadioSelect)
    theme = forms.ChoiceField(
        label=_("Theme"), choices=[("light", _("Light")), ("dark", _("Dark"))], widget=forms.RadioSelect
    )

    def __init__(self, devices, theme, **kwargs):
        kwargs.setdefault("prefix", "preview")
        super().__init__(initial={"device": devices[0], "theme": theme}, **kwargs)
        self.fields["device"].choices = [(device, DEVICES[device]) for device in devices]
