The development Docker image builds again with Playwright 1.65 and later,
which fails with `libatomic.so.1: cannot open shared object file`. The
generated `Dockerfile` now installs `libatomic1` before the browser. On an
affected project, run `phoxtail docker create dockerfile`, then
`phoxtail docker up --build`.
