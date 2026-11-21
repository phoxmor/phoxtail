A command that needs a program you have not installed (Docker, the Docker
Compose v2 plugin, uv, git, ssh, scp or rsync) now says which one and how
to get it, instead of failing with a Python traceback. It checks before it
changes anything: `phoxtail db pull`, for one, stops before it reaches the
server when local Docker is missing. `phoxtail net status` reports Docker
as unknown instead of crashing, `phoxtail docker create compose` still
writes the file without uv, and `phoxtail docker build`, `push` and
`release` tag the image `:latest` only, saying why, when git is missing.
`phoxtail docker release` now refuses to start without uv, rather than
building an image from a lockfile it could not refresh.
