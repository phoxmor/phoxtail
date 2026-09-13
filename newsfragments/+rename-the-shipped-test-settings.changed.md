The shared test settings are `phoxtail.core.testing`, not
`phoxtail.core.test_settings`. The old name starts with `test_`, so a project's
own pytest run would collect it out of site-packages. Shipped in the same
release, so only code written against the intermediate name is affected.
