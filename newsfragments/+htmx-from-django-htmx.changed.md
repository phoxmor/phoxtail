htmx is no longer bundled with phoxtail. It now comes from `django-htmx`, which
phoxtail already depends on, via its `{% htmx_script %}` tag — one copy instead
of two, at 2.0.10 instead of 2.0.8. Any project template that loads htmx with
`<script src="{% static 'phoxtail_core/js/htmx.min.js' %}">` must switch to
`{% htmx_script %}`; the static file is gone, and under
`ManifestStaticFilesStorage` a stale reference raises at render time.
