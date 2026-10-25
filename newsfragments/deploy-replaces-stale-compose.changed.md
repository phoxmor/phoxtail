`phoxtail server deploy` no longer keeps a stale compose file on the server.
When the server's `docker-compose.yaml` differs from the local one, it shows
the difference and asks before replacing it. `.env` and `nginx.conf` are still
uploaded only when the server has none: one holds the secrets, and the other
is the HTTPS configuration `phoxtail server ssl` wrote.
