from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class DashboardNavItem:
    label: str
    url_name: str
    icon: str
    order: int = 100
    mobile: bool = True
    center: bool = False


DEFAULT_WIDGET_TEMPLATE = "phoxtail_dashboard/widgets/widget.html"


@dataclass
class DashboardWidget:
    """A card on the dashboard index, advertising one of a module's views.

    The default template renders ``title``/``description``/``icon`` as a link
    to ``url_name``, so the common case needs no template of its own and no
    per-request work. Passing ``template_name`` opts out: a widget that draws
    something the default card cannot may also pass a ``context_function``,
    whose return value is merged into that template's context.

    ``name`` identifies the widget within its module so a site can drop or
    replace it (see ``DashboardModule.remove_widget``).

    ``title`` and ``description`` are read at import time (a module's
    ``dashboard.py`` runs during autodiscovery, before any request has a
    locale), so translated values must be lazy.
    """

    name: str = ""
    title: str = ""
    description: str = ""
    icon: str = ""
    url_name: str = ""
    template_name: str = DEFAULT_WIDGET_TEMPLATE
    context_function: Callable | None = None
    order: int = 100
    css_files: list = field(default_factory=list)

    def __post_init__(self):
        # The default template links the whole card, so a missing url_name
        # would raise NoReverseMatch at render time and take the dashboard
        # down for every user. Fail at import instead.
        if self.template_name == DEFAULT_WIDGET_TEMPLATE and not self.url_name:
            raise ValueError(f"Dashboard widget '{self.name or self.title}' needs a url_name.")


class DashboardModule:
    """One app's contribution to the dashboard: nav items, widgets and URLs.

    ``verbose_name`` is what the index prints above the module's widgets. It
    defaults to a readable form of ``app_name``, which is right often enough
    that most modules never set it — but a module whose key is an internal
    slug, or one that wants a translated heading, passes its own (lazily, as
    ``dashboard.py`` is imported before any request has a locale).
    """

    def __init__(self, app_name, url_prefix="", url_patterns=None, verbose_name=None):
        self.app_name = app_name
        self.verbose_name = verbose_name or app_name.replace("_", " ").replace("-", " ").title()
        self.url_prefix = url_prefix
        self.url_patterns = url_patterns or []
        self._nav_items = []
        self._widgets = []

    def add_nav_item(self, **kwargs):
        self._nav_items.append(DashboardNavItem(**kwargs))

    def add_widget(self, **kwargs):
        self._widgets.append(DashboardWidget(**kwargs))

    def remove_widget(self, name):
        """Drop one of this module's widgets by name.

        A site removes another app's widget from its own ``dashboard.py``,
        which autodiscovery imports after that app's — so the site app must
        come later in INSTALLED_APPS.
        """
        if not name:
            raise ValueError("remove_widget needs a widget name.")
        before = len(self._widgets)
        self._widgets = [widget for widget in self._widgets if widget.name != name]
        if len(self._widgets) == before:
            raise KeyError(f"Dashboard module '{self.app_name}' has no widget named '{name}'.")

    def remove_nav_item(self, label):
        """Drop one of this module's nav items by label."""
        before = len(self._nav_items)
        self._nav_items = [item for item in self._nav_items if item.label != label]
        if len(self._nav_items) == before:
            raise KeyError(f"Dashboard module '{self.app_name}' has no nav item labelled '{label}'.")


class DashboardRegistry:
    def __init__(self):
        self._modules = {}

    def register(self, module):
        if module.app_name in self._modules:
            raise ValueError(f"Dashboard module '{module.app_name}' is already registered.")
        self._modules[module.app_name] = module

    def unregister(self, app_name):
        """Remove a whole module — nav items, widgets and URLs alike.

        The escape hatch for a site that wants to replace an app's dashboard
        contribution wholesale rather than amend it.
        """
        try:
            del self._modules[app_name]
        except KeyError:
            raise KeyError(f"Dashboard module '{app_name}' is not registered.") from None

    def get_module(self, app_name):
        """Return a registered module so a site can amend it."""
        try:
            return self._modules[app_name]
        except KeyError:
            raise KeyError(f"Dashboard module '{app_name}' is not registered.") from None

    def get_nav_items(self):
        items = []
        for module in self._modules.values():
            items.extend(module._nav_items)
        return sorted(items, key=lambda x: x.order)

    def get_mobile_nav_items(self):
        items = []
        for module in self._modules.values():
            items.extend(item for item in module._nav_items if item.mobile)
        return sorted(items, key=lambda x: x.order)

    def get_url_patterns(self):
        return [(module.url_prefix, module.url_patterns) for module in self._modules.values() if module.url_patterns]

    def get_widgets(self):
        widgets = []
        for module in self._modules.values():
            widgets.extend(module._widgets)
        return sorted(widgets, key=lambda x: x.order)

    def get_widget_groups(self):
        """Widgets grouped under their module's heading.

        Groups are ordered by the first widget each contains, so a module
        places itself on the page through the same ``order`` its widgets
        already use — there is no second ordering to keep in sync.
        """
        groups = [
            {"title": module.verbose_name, "widgets": sorted(module._widgets, key=lambda x: x.order)}
            for module in self._modules.values()
            if module._widgets
        ]
        return sorted(groups, key=lambda group: group["widgets"][0].order)

    def get_widget_css_files(self):
        seen = set()
        files = []
        for widget in self.get_widgets():
            for css_file in widget.css_files:
                if css_file not in seen:
                    seen.add(css_file)
                    files.append(css_file)
        return files


registry = DashboardRegistry()
