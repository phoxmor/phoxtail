import pytest

from phoxtail.dashboard.registry import (
    DEFAULT_WIDGET_TEMPLATE,
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
        widget = DashboardWidget(template_name="test.html", context_function=lambda r: {})
        assert widget.order == 100
        assert widget.css_files == []

    def test_declarative_widget_needs_no_template_or_context_function(self):
        widget = DashboardWidget(name="profile", title="Profile", url_name="users:profile")
        assert widget.template_name == DEFAULT_WIDGET_TEMPLATE
        assert widget.context_function is None

    def test_default_template_without_url_name_raises(self):
        # NoReverseMatch at render would take the whole index down, so the
        # default template's contract is enforced at import.
        with pytest.raises(ValueError, match="needs a url_name"):
            DashboardWidget(name="broken", title="Broken")

    def test_custom_template_needs_no_url_name(self):
        widget = DashboardWidget(name="custom", template_name="own.html")
        assert widget.url_name == ""


class TestDashboardModule:
    def test_init(self):
        module = DashboardModule("booking", "booking/")
        assert module.app_name == "booking"
        assert module.url_prefix == "booking/"
        assert module.url_patterns == []
        assert module._nav_items == []
        assert module._widgets == []

    def test_verbose_name_derived_from_app_name(self):
        assert DashboardModule("booking").verbose_name == "Booking"
        assert DashboardModule("event_planning").verbose_name == "Event Planning"

    def test_verbose_name_explicit_wins(self):
        assert DashboardModule("users", verbose_name="Account").verbose_name == "Account"

    def test_url_prefix_optional_for_a_widget_only_module(self):
        module = DashboardModule("users")
        assert module.url_prefix == ""
        assert module.url_patterns == []

    def test_remove_widget(self):
        module = DashboardModule("booking", "booking/")
        module.add_widget(name="keep", title="Keep", url_name="a")
        module.add_widget(name="drop", title="Drop", url_name="b")

        module.remove_widget("drop")
        assert [w.name for w in module._widgets] == ["keep"]

    def test_remove_widget_unknown_raises(self):
        module = DashboardModule("booking", "booking/")
        with pytest.raises(KeyError, match="no widget named"):
            module.remove_widget("absent")

    def test_remove_widget_requires_a_name(self):
        # Every unnamed widget would match "" and be dropped together.
        module = DashboardModule("booking", "booking/")
        module.add_widget(title="Unnamed", url_name="a")
        with pytest.raises(ValueError, match="needs a widget name"):
            module.remove_widget("")

    def test_remove_nav_item(self):
        module = DashboardModule("booking", "booking/")
        module.add_nav_item(label="Keep", url_name="a", icon="a")
        module.add_nav_item(label="Drop", url_name="b", icon="b")

        module.remove_nav_item("Drop")
        assert [item.label for item in module._nav_items] == ["Keep"]

    def test_remove_nav_item_unknown_raises(self):
        module = DashboardModule("booking", "booking/")
        with pytest.raises(KeyError, match="no nav item labelled"):
            module.remove_nav_item("absent")

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
        module.add_nav_item(label="Events", url_name="events:list", icon="calendar", order=50)
        module.add_nav_item(label="Plans", url_name="plans:list", icon="plans", order=10)
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
        module.add_widget(template_name="b.html", context_function=lambda r: {}, order=200)
        module.add_widget(template_name="a.html", context_function=lambda r: {}, order=50)
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

    def test_get_module(self):
        reg = DashboardRegistry()
        module = DashboardModule("booking", "booking/")
        reg.register(module)
        assert reg.get_module("booking") is module

    def test_get_module_unknown_raises(self):
        reg = DashboardRegistry()
        with pytest.raises(KeyError, match="is not registered"):
            reg.get_module("absent")

    def test_unregister_removes_everything_the_module_contributed(self):
        reg = DashboardRegistry()
        module = DashboardModule("booking", "booking/", url_patterns=[("path/", lambda: None)])
        module.add_nav_item(label="Bookings", url_name="a", icon="a")
        module.add_widget(name="bookings", title="Bookings", url_name="a")
        reg.register(module)

        reg.unregister("booking")
        assert reg.get_nav_items() == []
        assert reg.get_widgets() == []
        assert reg.get_url_patterns() == []

    def test_unregister_unknown_raises(self):
        reg = DashboardRegistry()
        with pytest.raises(KeyError, match="is not registered"):
            reg.unregister("absent")

    def test_reregister_after_unregister(self):
        # The path a site takes to replace an app's contribution wholesale.
        reg = DashboardRegistry()
        reg.register(DashboardModule("booking", "booking/"))
        reg.unregister("booking")
        reg.register(DashboardModule("booking", "booking/", verbose_name="Studio"))
        assert reg.get_module("booking").verbose_name == "Studio"

    def test_get_widget_groups(self):
        reg = DashboardRegistry()
        account = DashboardModule("users", verbose_name="Account")
        account.add_widget(name="profile", title="Profile", url_name="a", order=100)
        booking = DashboardModule("booking", "booking/")
        booking.add_widget(name="plans", title="Plans", url_name="c", order=30)
        booking.add_widget(name="bookings", title="Bookings", url_name="b", order=10)
        reg.register(account)
        reg.register(booking)

        groups = reg.get_widget_groups()
        # Booking first: its earliest widget (10) precedes Account's (100),
        # despite Account registering first.
        assert [group["title"] for group in groups] == ["Booking", "Account"]
        assert [w.name for w in groups[0]["widgets"]] == ["bookings", "plans"]

    def test_get_widget_groups_skips_modules_without_widgets(self):
        reg = DashboardRegistry()
        module = DashboardModule("booking", "booking/")
        module.add_nav_item(label="Bookings", url_name="a", icon="a")
        reg.register(module)

        assert reg.get_widget_groups() == []

    def test_empty_registry(self):
        reg = DashboardRegistry()
        assert reg.get_nav_items() == []
        assert reg.get_mobile_nav_items() == []
        assert reg.get_url_patterns() == []
        assert reg.get_widgets() == []
        assert reg.get_widget_groups() == []
        assert reg.get_widget_css_files() == []
