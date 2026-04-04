"""
Service classes for reservation core business logic.
"""


class StaffService:
    """Service class for Staff business logic."""

    def __init__(self, staff):
        self.staff = staff

    def get_user_username(self):
        """Get the username of the staff user."""
        return self.staff.user.username if self.staff.user else ""

    def get_user_first_name(self):
        """Get the first name of the staff user."""
        return self.staff.user.first_name if self.staff.user else ""

    def get_user_last_name(self):
        """Get the last name of the staff user."""
        return self.staff.user.last_name if self.staff.user else ""

    def get_user_email(self):
        """Get the email of the staff user."""
        return self.staff.user.email if self.staff.user else ""

    def get_user_full_name(self):
        """Get the full name of the staff user."""
        return self.staff.user.get_full_name() if self.staff.user else ""
