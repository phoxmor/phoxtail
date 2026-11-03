`phoxtail server ssl` now puts `www.<domain>` on the certificate whenever it
points at the server, so `https://www.<domain>` no longer shows a browser
certificate warning. `--www` and `--no-www` override the choice, and one of
them is required with `--skip-dns-check`. A rerun adds any name the
certificate is missing and never removes one. The generated `nginx.conf`
serves `https://www.<domain>` only when the certificate covers it
(`phoxtail nginx create production --no-www` leaves it out). On a site whose
`https://www.<domain>` shows a warning, rerun `phoxtail server ssl <ip>`.
