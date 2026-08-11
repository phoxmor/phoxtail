from dataclasses import dataclass, field


@dataclass
class DashboardNavItem:
    label: str
    url_name: str
    icon: str
    order: int = 100
    mobile: bool = True
    center: bool = False


@dataclass
class DashboardWidget:
    template_name: str
    context_function: callable
    order: int = 100
    css_files: list = field(default_factory=list)


class DashboardModule:
    def __init__(self, app_name, url_prefix, url_patterns=None):
        self.app_name = app_name
        self.url_prefix = url_prefix
        self.url_patterns = url_patterns or []
        self._nav_items = []
        self._widgets = []

    def add_nav_item(self, **kwargs):
        self._nav_items.append(DashboardNavItem(**kwargs))

    def add_widget(self, **kwargs):
        self._widgets.append(DashboardWidget(**kwargs))


class DashboardRegistry:
    def __init__(self):
        self._modules = {}

    def register(self, module):
        if module.app_name in self._modules:
            raise ValueError(f"Dashboard module '{module.app_name}' is already registered.")
        self._modules[module.app_name] = module

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
