Production images no longer carry the project's secrets. The generated
Dockerfile copies the project folder into the image, and the generated
`.dockerignore` excluded `.env` only at the project root, while
`phoxtail server deploy` keeps the production `.env` (with `SECRET_KEY`
and the database password) in `.phoxtail/deploy/`. Anyone able to pull an
image built after a project's first `server deploy` could read those
files. The `.dockerignore` template now excludes `.env` files at any
depth, `.phoxtail/`, every hidden file or folder at the project root and
database dumps (`*.sql`), and `phoxtail docker push` and
`phoxtail docker release` now refuse to push an image with a `.env`,
`.env.*`, `.phoxtail` or `.sql` file under `/app`. Existing projects: run
`phoxtail docker create dockerignore --force` (then re-apply any edits of
your own), release again, change every credential that file holds (at
least `SECRET_KEY`, the database password and any email password) in both
copies of `.env`, on the server and in `.phoxtail/deploy/`, and delete the
old image versions from your registry. A database password must be
changed in the database itself as well: Postgres reads
`POSTGRES_PASSWORD` only when it first creates its volume.
