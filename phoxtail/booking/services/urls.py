from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    # Main list to view all available services
    path("", views.services_list_view, name="list"),
    # Detail view for a specific service
    path("<uuid:service_id>/", views.service_detail_view, name="detail"),
]
