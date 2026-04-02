from phoxtail.dashboard.templatetags.phoxtail_dashboard_tags import (
    dashboard_icon_path,
)


class TestDashboardIconPath:
    def test_returns_correct_path(self):
        result = dashboard_icon_path("calendar")
        assert result == "phoxtail_core/svgs/calendar.html"

    def test_different_icon(self):
        result = dashboard_icon_path("settings")
        assert result == "phoxtail_core/svgs/settings.html"
