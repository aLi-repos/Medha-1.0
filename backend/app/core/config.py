from dataclasses import dataclass, field
from os import getenv

from dotenv import load_dotenv


# Load variables from backend/.env before reading configuration.
load_dotenv()

# Canonical role → minimum (default) security mode mapping.
# Configurable via MEDHA_ROLE_SECURITY_MODES="role:mode,role:mode,...".
DEFAULT_ROLE_SECURITY_MODES: dict[str, str] = {
    "operator": "standard",
    "engineer": "standard",
    "junior_engineer": "standard",
    "senior_engineer": "sovereign",
    "manager": "sovereign",
    "admin": "sovereign",
    "hr": "secure",
    "monitor": "secure",
}

_SECURITY_MODE_ORDER: dict[str, int] = {"standard": 0, "secure": 1, "sovereign": 2}


def security_mode_order(mode: str) -> int:
    """Numeric order for security mode comparison (higher = stricter)."""
    return _SECURITY_MODE_ORDER.get(mode, 0)


def _parse_role_security_modes(raw: str | None) -> dict[str, str]:
    mapping = dict(DEFAULT_ROLE_SECURITY_MODES)
    if not raw:
        return mapping
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        role, mode = pair.split(":", 1)
        role, mode = role.strip(), mode.strip()
        if role and mode in _SECURITY_MODE_ORDER:
            mapping[role] = mode
    return mapping


@dataclass(frozen=True)
class Settings:
    """Configuration read from the local process environment."""

    app_name: str
    app_version: str
    environment: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    database_url: str
    role_security_modes: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ROLE_SECURITY_MODES))
    local_llm_base_url: str = "http://127.0.0.1:11434"
    local_llm_model: str = "qwen2.5:3b-instruct"
    local_llm_timeout: int = 30


def security_mode_for_role(role: str) -> str:
    """Return the effective default security mode for a role."""
    return settings.role_security_modes.get(role, "standard")


def _required_environment_value(name: str) -> str:
    value = getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured before starting MEDHA")
    return value


def _positive_integer_environment_value(name: str, default: int) -> int:
    raw_value = getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a positive integer") from error

    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")

    return value


settings = Settings(
    app_name=getenv("MEDHA_APP_NAME", "MEDHA Backend"),
    app_version=getenv("MEDHA_APP_VERSION", "0.1.0"),
    environment=getenv("MEDHA_ENV", "development"),
    jwt_secret=_required_environment_value("MEDHA_JWT_SECRET"),
    jwt_algorithm="HS256",
    jwt_expiration_minutes=_positive_integer_environment_value(
        "MEDHA_JWT_EXPIRATION_MINUTES",
        30,
    ),
    database_url=getenv("MEDHA_DATABASE_URL", "sqlite:///medha.db"),
    role_security_modes=_parse_role_security_modes(getenv("MEDHA_ROLE_SECURITY_MODES")),
    # Local open-weight LLM runtime (e.g. Ollama-compatible HTTP server).
    local_llm_base_url=getenv("MEDHA_LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434"),
    local_llm_model=getenv("MEDHA_LOCAL_LLM_MODEL", "qwen2.5:3b-instruct"),
    local_llm_timeout=_positive_integer_environment_value(
        "MEDHA_LOCAL_LLM_TIMEOUT",
        30,
    ),
)