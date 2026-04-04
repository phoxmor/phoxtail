from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    # Subscriptions
    path("", views.subscription_list_view, name="subscription-list"),
    path(
        "renew-subscription-form/<uuid:subscription_id>/",
        views.subscription_renew_form_view,
        name="renew-subscription-form",
    ),
    path(
        "create-subscription-form/",
        views.subscription_create_form_view,
        name="create-subscription-form",
    ),
    path(
        "create-subscription/",
        views.subscription_create_view,
        name="create-subscription",
    ),
    # Subscription Types
    path("type/", views.subscription_type_list_view, name="subscription-type-list"),
]
