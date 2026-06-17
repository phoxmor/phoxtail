import httpx
from django import forms
from django.utils.translation import gettext_lazy as _

from phoxtail.remotes.models import Remote


class RemoteAddForm(forms.ModelForm):
    token = forms.CharField(
        label=_("Token"),
        widget=forms.PasswordInput(render_value=False),
        help_text=_("Bearer token issued by the remote. Write-only — never shown after save."),
    )

    class Meta:
        model = Remote
        fields = ["name", "base_url", "token"]

    def clean_base_url(self):
        return self.cleaned_data["base_url"].rstrip("/")

    def clean(self):
        cleaned = super().clean()
        base_url = cleaned.get("base_url")
        token = cleaned.get("token")
        if not base_url or not token:
            return cleaned
        try:
            resp = httpx.get(
                f"{base_url}/api/ping/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
                follow_redirects=True,
            )
        except httpx.TimeoutException:
            raise forms.ValidationError(_("Connection timed out. Check the remote URL."))
        except httpx.ConnectError:
            raise forms.ValidationError(_("Could not reach %(url)s. Check the remote URL."), params={"url": base_url})
        except Exception as exc:
            raise forms.ValidationError(_("Connection failed: %(err)s"), params={"err": exc})
        if resp.status_code in (401, 403):
            raise forms.ValidationError(_("Authentication failed. Check your token."))
        if not resp.is_success:
            raise forms.ValidationError(
                _("Remote returned %(status)s. Make sure the URL points to a Phoxtail project."),
                params={"status": resp.status_code},
            )
        return cleaned


class RemoteEditForm(forms.ModelForm):
    token = forms.CharField(
        label=_("New Token"),
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=_("Leave blank to keep the current token."),
    )

    class Meta:
        model = Remote
        fields = ["name", "base_url", "token"]

    def clean_base_url(self):
        return self.cleaned_data["base_url"].rstrip("/")

    def clean_token(self):
        token = self.cleaned_data.get("token")
        if not token and self.instance and self.instance.pk:
            # keep the stored token when the field is left blank
            return self.instance.token
        return token
