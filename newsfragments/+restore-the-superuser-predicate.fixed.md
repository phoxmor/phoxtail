`phoxtail.api.auth.is_superuser` is available again. It was removed when the
last endpoint inside phoxtail stopped using it, which overlooked that apps
built on phoxtail import it too — for them the removal was a silent
`ImportError` at startup.
