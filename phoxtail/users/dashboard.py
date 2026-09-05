from django.utils.translation import gettext_lazy as _

from phoxtail.dashboard.registry import DashboardModule, registry

# A widget-only module: the users app mounts its own URLs, so it contributes
# no url_patterns here and needs no prefix.
module = DashboardModule(app_name="users", verbose_name=_("Account"))

module.add_widget(
    name="admin",
    title=_("Admin Dashboard"),
    description=_("Go to admin dashboard."),
    icon="settings",
    url_name="wagtailadmin_home",
    # Its own template only so the card can be hidden from users without
    # admin access; the markup is the default card's.
    template_name="phoxtail_dashboard/widgets/admin.html",
    order=90,
)

module.add_widget(
    name="profile",
    title=_("Your Profile"),
    description=_("Review and manage your information."),
    icon="person",
    url_name="users:profile",
    order=100,
)

module.add_widget(
    name="password",
    title=_("Change Password"),
    description=_("Choose a new password for your account."),
    icon="lock",
    url_name="account_change_password",
    order=110,
)

module.add_widget(
    name="email",
    title=_("Manage Email"),
    description=_("Add, remove and verify your email addresses."),
    icon="email",
    url_name="account_email",
    order=120,
)

registry.register(module)
