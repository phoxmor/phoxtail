import re
from urllib.parse import unquote

from django import template
from wagtail.models import Page

register = template.Library()


@register.filter
def decode_url(value):
    """Decode URL-encoded strings"""
    if not isinstance(value, str):
        return value
    return unquote(value)


@register.simple_tag(takes_context=True)
def has_active_child(context, items, request_path):
    """Check if any child page in a dropdown matches the current path"""
    decoded_request_path = decode_url(request_path)
    request = context.get("request")

    for item in items:
        if item.block_type == "internal_link":
            page = item.value.get("page")
            if page and isinstance(page, Page):
                # Use the same URL generation logic as pageurl tag
                page_url = page.get_url(request=request)
                decoded_page_url = decode_url(page_url)
                if decoded_request_path == decoded_page_url:
                    return True

    return False


@register.filter(name="add_class")
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})


@register.filter(name="to_object_position")
def to_object_position(background_position_style):
    return background_position_style.replace("background", "object")


@register.filter(name="cover")
def cover(img):
    horz = 50
    vert = 50
    focal_point = img.focal_point
    if focal_point:
        horz = int((focal_point.x * 100) // img.width)
        vert = int((focal_point.y * 100) // img.height)

    return (
        f"position: absolute; width: 100%; height: 100%; object-fit: cover;"
        f" object-position: {horz}% {vert}%;"
    )


@register.filter(name="get_filename_from_path")
def get_filename_from_path(value):
    """Returns just the filename from a path"""
    try:
        return value.name.split("/")[-1]
    except (AttributeError, IndexError):
        return value


# Embed tags

youtube_domains = [
    "https://youtu.be",
    "https://www.youtu.be",
    "https://www.youtube.com",
    "https://youtube.com",
]

google_maps_domains = [
    "https://google.com/maps",
    "https://www.google.com/maps",
]


@register.filter
def is_youtube_url(url: str) -> bool:
    """
    Template tag that checks if a URL is from YouTube.

    Args:
        url (str): The URL to check

    Returns:
        bool: True if the URL is from YouTube, False otherwise
    """
    return any(url.startswith(domain) for domain in youtube_domains)


@register.filter
def is_google_maps_url(url: str) -> bool:
    """
    Template tag that checks if a URL is from Google Maps.

    Args:
        url (str): The URL to check

    Returns:
        bool: True if the URL is from Google Maps, False otherwise
    """
    return any(url.startswith(domain) for domain in google_maps_domains)


def extract_src_from_embed_code(embed_code: str) -> str:
    """
    Extracts the src attribute from an embed code.

    Args:
        embed_code (str): The HTML embed code containing a src attribute

    Returns:
        str: The src attribute value
    """
    # Regular expression to find src attribute
    src_pattern = r'src=["\'](.*?)["\']'
    match = re.search(src_pattern, embed_code)

    if not match:
        return None

    return match.group(1)


@register.filter
def is_youtube_embed(embed_code: str) -> bool:
    """
    Template tag that extracts the src attribute from an embed code and checks
    if it's from YouTube.

    Args:
        embed_code (str): The HTML embed code containing a src attribute

    Returns:
        bool: True if the src attribute is from YouTube, False otherwise
    """

    src_url = extract_src_from_embed_code(embed_code)

    return any(src_url.startswith(domain) for domain in youtube_domains)


@register.filter
def is_google_maps_embed(embed_code: str) -> bool:
    """
    Template tag that extracts the src attribute from an embed code and checks
    if it's from Google Maps.

    Args:
        embed_code (str): The HTML embed code containing a src attribute

    Returns:
        bool: True if the src attribute is from Google Maps, False otherwise
    """
    # Regular expression to find src attribute
    src_pattern = r'src=["\'](.*?)["\']'
    match = re.search(src_pattern, embed_code)

    if not match:
        return False

    src_url = match.group(1)

    return any(src_url.startswith(domain) for domain in google_maps_domains)


@register.filter
def max_items(block_value):
    """
    Calculate the maximum number of schedule items across all day_schedule blocks.
    Returns 0 if no items or invalid input.
    """
    max_count = 0
    try:
        for item in block_value:
            item_count = len(item.value.get("items", []))
            max_count = max(max_count, item_count)
        return max_count
    except (TypeError, AttributeError):
        return 0


@register.filter
def max_time_slots(block_value):
    """
    Calculate the maximum number of time slots across all day_schedule blocks.
    Returns 0 if no items or invalid input.
    """
    max_count = 0
    try:
        for item in block_value:
            item_count = len(item.value.get("time_slots", []))
            max_count = max(max_count, item_count)
        return max_count
    except (TypeError, AttributeError):
        return 0


@register.filter
def generate_range(value):
    """
    Generate a range from 0 to the given value for row iteration.
    Returns an empty list if input is invalid or non-positive.
    """
    try:
        value = int(value)
        if value <= 0:
            return []
        return range(value)
    except (TypeError, ValueError):
        return []


@register.filter
def get_item_at_index(items, index):
    """
    Safely get the item at the given index from a list or queryset.
    Returns None if index is invalid or item doesn't exist.
    """
    try:
        return items[int(index)]
    except (IndexError, TypeError, ValueError):
        return None


@register.filter
def expand_for_animation(partners, min_count=5):
    """
    Expand the partners list by repeating it until we have at least min_count items.

    Args:
        partners: The original list of partners
        min_count: Minimum number of items needed (default: 5)

    Returns:
        Expanded list with at least min_count items
    """
    if not partners:
        return partners

    original_count = len(partners)

    # If we already have enough partners, return as is
    if original_count >= min_count:
        return partners

    # Calculate how many times we need to repeat the list
    multiplier = (min_count + original_count - 1) // original_count  # Ceiling division

    # Examples:
    # 1 partner: (5 + 1 - 1) // 1 = 5 (repeats 5 times = 5 total)
    # 2 partners: (5 + 2 - 1) // 2 = 3 (repeats 3 times = 6 total)
    # 3 partners: (5 + 3 - 1) // 3 = 2 (repeats 2 times = 6 total)
    # 4 partners: (5 + 4 - 1) // 4 = 2 (repeats 2 times = 8 total)

    # Create the expanded list
    expanded_partners = []
    for i in range(multiplier):
        expanded_partners.extend(partners)

    return expanded_partners


@register.filter
def distribute_to_columns(images, num_columns=3):
    """
    Distribute images across columns for masonry-style layout.
    Uses a greedy algorithm to balance column heights.
    """
    if not images:
        return []

    # Initialize columns with empty lists and height trackers
    columns = [[] for _ in range(num_columns)]
    column_heights = [0] * num_columns

    for original_index, image in enumerate(images):
        # Calculate aspect ratio and estimated height
        if image.height == 0:
            aspect_ratio = 1.0
        else:
            aspect_ratio = image.width / image.height

        # Assume a fixed width (400px) and calculate proportional height
        # Add some padding for gaps between images
        estimated_height = (400 / aspect_ratio) + 16  # 16px for gap

        # Find the column with the shortest current height
        shortest_column_index = column_heights.index(min(column_heights))

        # Add image to the shortest column with original index preserved
        columns[shortest_column_index].append(
            {
                "image": image,
                "aspect_ratio": aspect_ratio,
                "estimated_height": estimated_height,
                "original_index": original_index,
            }
        )

        # Update column height
        column_heights[shortest_column_index] += estimated_height

    return columns


@register.simple_tag
def gallery_responsive_config(
    images, columns_small=1, columns_medium=2, columns_large=3
):
    """
    Processes gallery images and column configurations for different screen sizes.
    Usage: {% gallery_responsive_config block.value.images  # noqa: E501
        columns_small=block.value.columns_small
        columns_medium=block.value.columns_medium
        columns_large=block.value.columns_large as gallery_data %}
    """
    if not images:
        return {
            "small": [],
            "medium": [],
            "large": [],
            "columns_small": columns_small,
            "columns_medium": columns_medium,
            "columns_large": columns_large,
        }

    return {
        "small": distribute_to_columns(images, columns_small),
        "medium": distribute_to_columns(images, columns_medium),
        "large": distribute_to_columns(images, columns_large),
        "columns_small": columns_small,
        "columns_medium": columns_medium,
        "columns_large": columns_large,
    }
