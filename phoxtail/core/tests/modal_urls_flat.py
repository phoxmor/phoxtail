"""The same probe view, mounted without a language prefix."""

from django.urls import path

from phoxtail.core.tests.modal_urls import probe

urlpatterns = [path("probe/", probe, name="probe")]
