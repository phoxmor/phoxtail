`phoxtail server deploy` now checks that the server can actually read the image
from the registry, rather than assuming a login exists because `ghcr.io` appears
in `~/.docker/config.json`. An expired token, or one with no access to the
package, previously reported success and failed later at pull time with
`denied`.
