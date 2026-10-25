Security: generated Dockerfiles install packages with uv 0.13.5, which no
longer trusts the distrusted emSign certificate authority. An existing
project takes the fix by regenerating its Dockerfile with
`phoxtail docker create dockerfile --force`, which overwrites any local edits,
so diff it against a copy first.
