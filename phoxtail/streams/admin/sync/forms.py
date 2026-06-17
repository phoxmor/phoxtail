from django import forms

from phoxtail.core.fields import SingleSelectSearchField
from phoxtail.remotes.models import Remote


class RemoteSelectForm(forms.Form):
    remote = SingleSelectSearchField(
        queryset=Remote.objects.all(),
        required=False,
    )
