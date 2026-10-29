The generated `.dockerignore` now excludes Python caches (`__pycache__`,
`*.pyc`), `node_modules` and editor files at any depth, not only at the
project root, so bytecode compiled on the developer's machine no longer
ends up in images.
