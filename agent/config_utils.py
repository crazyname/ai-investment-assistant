from pathlib import Path
import os


PROJECT_DIR = Path(__file__).resolve().parent
PRIVATE_CONFIG_FILE = PROJECT_DIR / "private_config.txt"


def load_private_config(path: Path = PRIVATE_CONFIG_FILE) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from the local private config file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_config_value(key: str, default: str = "") -> str:
    return os.getenv(key) or load_private_config().get(key, default)


def apply_proxy_from_config() -> None:
    for key in ("HTTP_PROXY", "HTTPS_PROXY"):
        value = get_config_value(key)
        if value:
            os.environ[key] = value
