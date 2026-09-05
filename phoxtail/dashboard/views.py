from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .registry import registry


@login_required
def dashboard_view(request):
    def render_data(widget):
        # A widget that only advertises a view has nothing to compute; only a
        # custom template ever needs a context_function.
        context_data = widget.context_function(request) if widget.context_function else {}
        return {
            "template_name": widget.template_name,
            "name": widget.name,
            "title": widget.title,
            "description": widget.description,
            "icon": widget.icon,
            "url_name": widget.url_name,
            "order": widget.order,
            **context_data,
        }

    groups = [
        {"title": group["title"], "widgets": [render_data(widget) for widget in group["widgets"]]}
        for group in registry.get_widget_groups()
    ]
    return render(
        request,
        "phoxtail_dashboard/index.html",
        {
            "dashboard_widget_groups": groups,
            # The same widgets ungrouped, for a site whose own template wants
            # one flat run of cards — in widget order, since the headings that
            # justify the grouped order are not there to explain it.
            "dashboard_widgets": sorted(
                (widget for group in groups for widget in group["widgets"]),
                key=lambda widget: widget["order"],
            ),
            "widget_css_files": registry.get_widget_css_files(),
        },
    )
