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


class Occurrence(models.Model):
    """Something that happens at a place: a moment, and the zone of that place's clocks."""

    start_datetime = models.DateTimeField()
    zone = models.CharField(max_length=64)
