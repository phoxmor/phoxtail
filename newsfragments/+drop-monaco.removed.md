The Monaco code editor is gone from the Wagtail admin. The HTML, CSS and
JavaScript fields on a block variant now use a fixed-height text area instead of
an embedded editor, which drops a bundled JavaScript loader and a runtime fetch
from a third-party CDN. No data or schema changes: the fields are unchanged and
their content is untouched.
