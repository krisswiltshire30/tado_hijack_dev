"""Constants for Tado Hijack."""

from typing import Final

DOMAIN: Final = "tado_hijack"

# Library Specifics
TADO_VERSION_PATCH: Final = "0.2.2"
TADO_USER_AGENT: Final = f"HomeAssistant/{TADO_VERSION_PATCH}"

# Configuration Keys
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_SLOW_POLL_INTERVAL: Final = "slow_poll_interval"
CONF_OFFSET_POLL_INTERVAL: Final = "offset_poll_interval"
CONF_THROTTLE_THRESHOLD: Final = "throttle_threshold"
CONF_DISABLE_POLLING_WHEN_THROTTLED: Final = "disable_polling_when_throttled"

# Default Intervals
DEFAULT_SCAN_INTERVAL: Final = 3600
DEFAULT_SLOW_POLL_INTERVAL: Final = 24  # Hours
DEFAULT_OFFSET_POLL_INTERVAL: Final = 0  # Hours (0 = disabled)
DEFAULT_THROTTLE_THRESHOLD: Final = (
    0  # 0 = disabled, >0 = throttle when remaining < threshold
)

# Minimums (scan_interval 0 = no periodic poll, offset 0 = disabled)
MIN_SCAN_INTERVAL: Final = 0
MIN_SLOW_POLL_INTERVAL: Final = 1  # Hour
MIN_OFFSET_POLL_INTERVAL: Final = 0  # 0 = disabled

# Timing & Logic
DEBOUNCE_COOLDOWN_S: Final = 5
OPTIMISTIC_GRACE_PERIOD_S: Final = 30
PROTECTION_MODE_TEMP: Final = 5.0  # Minimum safe temperature for manual override
SLOW_POLL_CYCLE_S: Final = 86400  # 24 Hours in seconds

# Service Names
SERVICE_MANUAL_POLL: Final = "manual_poll"
SERVICE_RESUME_ALL_SCHEDULES: Final = "resume_all_schedules"

# Device Capabilities
CAPABILITY_INSIDE_TEMP: Final = "INSIDE_TEMPERATURE_MEASUREMENT"
TEMP_OFFSET_ATTR: Final = "temperatureOffset"
