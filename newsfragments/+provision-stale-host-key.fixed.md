`phoxtail server provision` now drops any `known_hosts` entry for a freshly
created server's IP before connecting. Providers recycle addresses, and a
leftover key made SSH refuse the connection outright — reported as a timeout,
which sent you looking at the wrong thing. A failed SSH wait now quotes what
SSH actually said.
