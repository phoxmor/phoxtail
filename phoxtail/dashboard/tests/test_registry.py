import pytest

from phoxtail.dashboard.registry import (
    DashboardModule,
    DashboardNavItem,
    DashboardRegistry,
    DashboardWidget,
)


class TestDashboardNavItem:
    def test_defaults(self):
        item = DashboardNavItem(label="Home", url_name="home", icon="home")
        assert item.order == 100
        assert item.mobile is True

    def test_custom_values(self):
        item = DashboardNavItem(
            label="Events",
            url_name="events:list",
            icon="calendar",
            order=50,
            mobile=False,
        )
        assert item.label == "Events"
        assert item.order == 50
        assert item.mobile is False


class TestDashboardWidget:
    def test_defaults(self):
        widget = DashboardWidget(
            template_name="test.html", context_function=lambda r: {}
        )
        assert widget.order == 100
        assert widget.css_files == []


class TestDashboardModule:
    def test_init(self):
        module = DashboardModule("booking", "booking/")
        assert module.app_name == "booking"
        assert module.url_prefix == "booking/"
        assert module.url_patterns == []
        assert module._nav_items == []
        assert module._widgets == []

    def test_add_nav_item(self):
        module = DashboardModule("booking", "booking/")
        module.add_nav_item(label="Events", url_name="events:list", icon="calendar")
        assert len(module._nav_items) == 1
        assert module._nav_items[0].label == "Events"

    def test_add_widget(self):
        def ctx_fn(r):
            return {"data": "test"}

        module = DashboardModule("booking", "booking/")
        module.add_widget(template_name="widget.html", context_function=ctx_fn)
        assert len(module._widgets) == 1
        assert module._widgets[0].template_name == "widget.html"


class TestDashboardRegistry:
    def test_register_and_get_nav_items(self):
        reg = DashboardRegistry()
        module = DashboardModule("booking", "booking/")
        module.add_nav_item(
            label="Events", url_name="events:list", icon="calendar", order=50
        )
        module.add_nav_item(
            label="Plans", url_name="plans:list", icon="plans", order=10
        )
        reg.register(module)

        items = reg.get_nav_items()
        assert len(items) == 2
        assert items[0].label == "Plans"  # order=10 first
        assert items[1].label == "Events"  # order=50 second

    def test_duplicate_registration_raises(self):
        reg = DashboardRegistry()
        module1 = DashboardModule("booking", "booking/")
        module2 = DashboardModule("booking", "booking/")
        reg.register(module1)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(module2)

    def test_get_mobile_nav_items_filters(self):
        reg = DashboardRegistry()
        module = DashboardModule("test", "test/")
        module.add_nav_item(label="Mobile", url_name="a", icon="a", mobile=True)
        module.add_nav_item(label="Desktop", url_name="b", icon="b", mobile=False)
        reg.register(module)

        mobile_items = reg.get_mobile_nav_items()
        assert len(mobile_items) == 1
        assert mobile_items[0].label == "Mobile"

    def test_get_url_patterns(self):
        reg = DashboardRegistry()
        patterns = [("path/", lambda: None)]
        module = DashboardModule("booking", "booking/", url_patterns=patterns)
        reg.register(module)

        url_patterns = reg.get_url_patterns()
        assert len(url_patterns) == 1
        assert url_patterns[0][0] == "booking/"

    def test_get_url_patterns_excludes_empty(self):
        reg = DashboardRegistry()
        module = DashboardModule("empty", "empty/")
        reg.register(module)

        assert reg.get_url_patterns() == []

    def test_get_widgets_sorted(self):
        reg = DashboardRegistry()
        module = DashboardModule("test", "test/")
        module.add_widget(
            template_name="b.html", context_function=lambda r: {}, order=200
        )
        module.add_widget(
            template_name="a.html", context_function=lambda r: {}, order=50
        )
        reg.register(module)

        widgets = reg.get_widgets()
        assert widgets[0].template_name == "a.html"
        assert widgets[1].template_name == "b.html"

    def test_get_widget_css_files_deduplicates(self):
        reg = DashboardRegistry()
        module = DashboardModule("test", "test/")
        module.add_widget(
            template_name="a.html",
            context_function=lambda r: {},
            css_files=["style.css", "shared.css"],
        )
        module.add_widget(
            template_name="b.html",
            context_function=lambda r: {},
            css_files=["shared.css", "other.css"],
        )
        reg.register(module)

        css_files = reg.get_widget_css_files()
        assert css_files == ["style.css", "shared.css", "other.css"]

    def test_empty_registry(self):
        reg = DashboardRegistry()
        assert reg.get_nav_items() == []
        assert reg.get_mobile_nav_items() == []
        assert reg.get_url_patterns() == []
        assert reg.get_widgets() == []
        assert reg.get_widget_css_files() == []
