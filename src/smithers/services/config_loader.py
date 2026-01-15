"""Configuration file loader for Smithers."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from smithers.logging_config import get_logger

logger = get_logger("smithers.services.config_loader")

CONFIG_FILE = Path.home() / ".smithers" / "config.json"


@dataclass
class VibekanbanConfig:
    """Vibekanban-specific configuration."""

    enabled: bool = False
    project_id: str | None = None


def load_vibekanban_config() -> VibekanbanConfig:
    """Load vibekanban configuration from config file and environment.

    Environment variables override file config:
    - SMITHERS_VIBEKANBAN_ENABLED: "1" or "true" to enable
    - SMITHERS_VIBEKANBAN_PROJECT_ID: Project ID to use

    Returns:
        VibekanbanConfig with values from file or defaults.
    """
    file_config = _load_from_file()

    # Environment variables override file config
    env_enabled = os.environ.get("SMITHERS_VIBEKANBAN_ENABLED")
    env_project_id = os.environ.get("SMITHERS_VIBEKANBAN_PROJECT_ID")

    enabled = file_config.enabled
    if env_enabled is not None:
        enabled = env_enabled.lower() in ("1", "true", "yes")

    project_id = env_project_id or file_config.project_id

    return VibekanbanConfig(
        enabled=enabled,
        project_id=project_id,
    )


def _load_from_file() -> VibekanbanConfig:
    """Load configuration from the config file.

    Returns:
        VibekanbanConfig with values from file or defaults.
    """
    if not CONFIG_FILE.exists():
        logger.debug(f"Config file not found: {CONFIG_FILE}")
        return VibekanbanConfig()

    try:
        with CONFIG_FILE.open() as f:
            data = json.load(f)

        vk_config = data.get("vibekanban", {})
        return VibekanbanConfig(
            enabled=vk_config.get("enabled", False),
            project_id=vk_config.get("project_id"),
        )
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load config file: {e}")
        return VibekanbanConfig()
