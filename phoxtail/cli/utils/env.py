"""Environment file reading utilities."""

from pathlib import Path


def read_env_value(key: str, env_file: Path = Path(".env")) -> str | None:
    """Read a value from an environment file.

    Handles quoting (single and double quotes) and ignores comments.
    Returns None if the file doesn't exist or the key isn't found.
    """
    if not env_file.exists():
        return None

    try:
        content = env_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            line_key, _, line_value = line.partition("=")
            if line_key.strip() == key:
                value = line_value.strip().strip('"').strip("'")
                if value:
                    return value
    except Exception:
        pass

    return None
