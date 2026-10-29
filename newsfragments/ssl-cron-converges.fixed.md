`phoxtail server ssl` now replaces an outdated certificate-renewal cron line
instead of keeping it: it shows the server's line next to the current one and
asks before replacing it, leaving every other cron entry as it is. On a
server set up before 0.3.0, running `phoxtail server ssl <ip>` is now how the
`--no-deps` renewal line arrives; no `crontab -e` edit is needed.
