from django.urls import path

from .views import (
    get_customer_reviews_block_modal_content_with_htmx,
    get_image_gallery_block_modal_content_with_htmx,
    get_team_members_block_modal_content_with_htmx,
)

app_name = "app"

urlpatterns = [
    path(
        "htmx-partials/image-gallery-modal-content/",
        get_image_gallery_block_modal_content_with_htmx,
        name="image_gallery_modal_content",
    ),
    path(
        "htmx-partials/customer-reviews-modal-content/",
        get_customer_reviews_block_modal_content_with_htmx,
        name="customer_reviews_modal_content",
    ),
    path(
        "htmx-partials/team-members-modal-content/",
        get_team_members_block_modal_content_with_htmx,
        name="team_members_modal_content",
    ),
]
