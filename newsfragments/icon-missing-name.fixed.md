A page whose block variant names an icon that no longer exists now renders
without that icon instead of failing with a server error. The `{% icon %}`
tag logs a warning naming the missing icon, so stored variants that still
use a name removed in an earlier release can be found and fixed.
