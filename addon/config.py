from aqt import mw
from .constants import (
    AUTO_SYNC_CONFIG_NAME,
    CONFIG_STRICTLY_AVOID_INTERRUPTIONS,
    CONFIG_SYNC_ON_CHANGE_ONLY,
    CONFIG_DEFAULT_CONFIG,
    CONFIG_MAXIMUMS,
    CONFIG_MINIMUMS,
)


class AutoSyncConfigManager:
    """Manages accessing the addons configuration in Ankis config storage"""

    _BOOL_CONFIG_KEYS = frozenset(
        {
            CONFIG_STRICTLY_AVOID_INTERRUPTIONS,
            CONFIG_SYNC_ON_CHANGE_ONLY,
        }
    )

    _INT_CONFIG_KEYS = frozenset(CONFIG_DEFAULT_CONFIG) - _BOOL_CONFIG_KEYS

    def __init__(self, mw: mw):
        """Load the config with default return value and in case it's the first run, save it to Anki"""
        self.mw = mw
        self.col = mw.col

        # Load existing config or use default
        current_config = self.col.get_config(
            AUTO_SYNC_CONFIG_NAME,
            default=dict(CONFIG_DEFAULT_CONFIG),
        )
        if not isinstance(current_config, dict):
            current_config = {}

        # Migration for version 3: safer server defaults
        if current_config.get(CONFIG_CONFIG_VERSION, 0) < 3:
            current_config[CONFIG_IDLE_SYNC_TIMEOUT] = 60
            current_config[CONFIG_SYNC_ON_CHANGE_ONLY] = True
            current_config[CONFIG_IDLE_BEFORE_SYNC] = 10
            current_config[CONFIG_CONFIG_VERSION] = 3

        # Merge default config into current config for any missing keys (migrations)
        self.config = self._sanitize_config(current_config)

        # Save merged config
        self._save()

    def _save(self):
        self.col.set_config(AUTO_SYNC_CONFIG_NAME, self.config)

    def _sanitize_config(self, raw_config):
        merged = {**CONFIG_DEFAULT_CONFIG, **raw_config}
        sanitized = {}

        for key, default_value in CONFIG_DEFAULT_CONFIG.items():
            value = merged.get(key, default_value)
            if key in self._BOOL_CONFIG_KEYS:
                value = self._coerce_bool(value, default_value)
            elif key in self._INT_CONFIG_KEYS:
                value = self._coerce_int(value, default_value)

            minimum = CONFIG_MINIMUMS.get(key)
            if minimum is not None:
                value = max(minimum, value)

            maximum = CONFIG_MAXIMUMS.get(key)
            if maximum is not None:
                value = min(maximum, value)

            sanitized[key] = value

        return sanitized

    @staticmethod
    def _coerce_bool(value, default):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    @staticmethod
    def _coerce_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get(self, key):
        """get the value of the given config key"""
        return self.config[key]

    def set(self, key, val):
        """set the value of the given config key"""
        if key not in CONFIG_DEFAULT_CONFIG:
            raise KeyError(f"Unknown config key: {key}")
        updated_config = dict(self.config)
        updated_config[key] = val
        self.config = self._sanitize_config(updated_config)
        self._save()
