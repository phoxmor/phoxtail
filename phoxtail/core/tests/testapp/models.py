from django.db import models


class TestAdminPermission(models.Model):
    """
    ContentType anchor for test permissions. Never instantiated —
    exists only so Django creates Permission rows in auth_permission
    during migrate.
    """

    class Meta:
        default_permissions = ()
        permissions = [
            ("access_test_management", "Can access test management"),
            ("manage_test_items", "Can manage test items"),
        ]
