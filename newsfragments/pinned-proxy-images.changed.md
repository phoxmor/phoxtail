Generated production compose files pin `nginx:1.31` and
`certbot/certbot:v5.8.0` instead of taking whatever is newest, so a deploy can
no longer move a site to a new release line unasked; fixes within nginx 1.31
still arrive with every pull while that line is maintained. A deployed project
takes the pins by regenerating its compose file with
`phoxtail docker create compose production --registry --output .phoxtail/deploy/docker-compose.prod.yaml --force`
and deploying again.
