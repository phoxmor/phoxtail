from unittest.mock import MagicMock, patch

from phoxtail.dashboard.context_processors import dashboard_nav


class TestDashboardNav:
    @patch("phoxtail.dashboard.context_processors.registry")
    def test_returns_expected_keys(self, mock_registry):
        mock_registry.get_nav_items.return_value = ["item1"]
        mock_registry.get_mobile_nav_items.return_value = ["mobile1"]

        request = MagicMock()
        result = dashboard_nav(request)

        assert "dashboard_nav_items" in result
        assert "dashboard_mobile_nav_items" in result
        assert result["dashboard_nav_items"] == ["item1"]
        assert result["dashboard_mobile_nav_items"] == ["mobile1"]

    @patch("phoxtail.dashboard.context_processors.registry")
    def test_empty_registry(self, mock_registry):
        mock_registry.get_nav_items.return_value = []
        mock_registry.get_mobile_nav_items.return_value = []

        request = MagicMock()
        result = dashboard_nav(request)

        assert result["dashboard_nav_items"] == []
        assert result["dashboard_mobile_nav_items"] == []
