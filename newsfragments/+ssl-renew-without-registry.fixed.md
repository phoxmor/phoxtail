Certificate renewal no longer depends on the registry. The renewal cron and
`phoxtail ssl renew` started certbot together with nginx and web, and web's
`pull_policy: always` made every renewal pull the site image first — so once the
server's registry token expired, renewal failed silently and certificates
lapsed. Certbot now runs with `--no-deps`.

The cron line is only installed once, so re-running `phoxtail server ssl` does
not update an existing server. On each server, replace the
`# phoxtail-ssl-<project>` line in `crontab -e` with:

    0 3 1,15 * * cd $HOME/<project> && docker compose run --rm -T --no-deps certbot renew -q && docker compose exec -T nginx nginx -s reload  # phoxtail-ssl-<project>
