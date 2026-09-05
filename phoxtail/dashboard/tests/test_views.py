from unittest.mock import MagicMock, patch

from phoxtail.dashboard.registry import DashboardModule
from phoxtail.dashboard.views import dashboard_view


def render_context(modules):
    """Run the index view over the given modules and return its context.

    ``login_required`` is stepped around rather than satisfied: the view's own
    work is turning registered widgets into template data, and that needs no
    session.
    """
    registry = MagicMock()
    registry.get_widget_groups.return_value = [
        {"title": module.verbose_name, "widgets": module._widgets} for module in modules
    ]
    registry.get_widget_css_files.return_value = []

    with (
        patch("phoxtail.dashboard.views.registry", registry),
        patch("phoxtail.dashboard.views.render") as render,
    ):
        dashboard_view.__wrapped__(MagicMock())
    return render.call_args[0][2]


class TestDashboardView:
    def test_widgets_are_grouped_under_their_module(self):
        account = DashboardModule("users", verbose_name="Account")
        account.add_widget(name="profile", title="Profile", url_name="users:profile", order=100)
        booking = DashboardModule("booking", "booking/")
        booking.add_widget(name="bookings", title="Bookings", url_name="b", order=10)

        groups = render_context([booking, account])["dashboard_widget_groups"]

        assert [group["title"] for group in groups] == ["Booking", "Account"]
        assert groups[0]["widgets"][0]["title"] == "Bookings"
        assert groups[0]["widgets"][0]["url_name"] == "b"

    def test_flat_widgets_are_in_order_across_modules(self):
        # No headings to explain the grouped order, so the flat list is sorted
        # on its own terms.
        account = DashboardModule("users", verbose_name="Account")
        account.add_widget(name="profile", title="Profile", url_name="a", order=20)
        booking = DashboardModule("booking", "booking/")
        booking.add_widget(name="bookings", title="Bookings", url_name="b", order=10)
        booking.add_widget(name="plans", title="Plans", url_name="c", order=30)

        widgets = render_context([account, booking])["dashboard_widgets"]

        assert [widget["name"] for widget in widgets] == ["bookings", "profile", "plans"]

    def test_context_function_is_optional(self):
        module = DashboardModule("users", verbose_name="Account")
        module.add_widget(name="profile", title="Profile", url_name="a")

        widgets = render_context([module])["dashboard_widgets"]

        assert widgets[0]["template_name"] == "phoxtail_dashboard/widgets/widget.html"

    def test_context_function_output_is_merged_in(self):
        module = DashboardModule("booking", "booking/")
        module.add_widget(
            name="calendar",
            template_name="own.html",
            context_function=lambda request: {"events": [1, 2]},
        )

        widgets = render_context([module])["dashboard_widgets"]

        assert widgets[0]["events"] == [1, 2]
