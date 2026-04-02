from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .registry import registry


@login_required
def dashboard_view(request):
    widgets = []
    for widget in registry.get_widgets():
        context_data = widget.context_function(request)
        widgets.append(
            {
                "template_name": widget.template_name,
                "order": widget.order,
                **context_data,
            }
        )
    return render(
        request,
        "phoxtail_dashboard/index.html",
        {
            "dashboard_widgets": widgets,
            "widget_css_files": registry.get_widget_css_files(),
        },
    )
