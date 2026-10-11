The message classes are renamed from `auth-toast*` to phx names: `phx-toast`
(with `--hidden`, `--error`, `--success`, `--warning`, `--info`),
`phx-toast__body`, `phx-toast__label`, `phx-toast__text`, `phx-toast-container`
and `phx-toast-list`. A site that styles or selects the old classes must use
the new ones.
