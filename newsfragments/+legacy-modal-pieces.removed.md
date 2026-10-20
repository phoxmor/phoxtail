The old admin paginator template (`phoxtail_core/admin/partials/paginator.html`)
and the `.phoxtail-btn` and `.phoxtail-danger-section` rules in `modal.css` are
removed; nothing draws them any more. A list uses `{% paginator %}`, a button
`.phx-button`, and a danger zone is a `phx-card` with a `--danger` button.
