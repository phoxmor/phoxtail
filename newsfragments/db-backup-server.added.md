`phoxtail db backup <ip>` backs up a server's database: it dumps it into the
server's `db-backups/`, keeps it there, and copies it into the local
`db-backups/`. Without an IP it backs up the local database as before.
