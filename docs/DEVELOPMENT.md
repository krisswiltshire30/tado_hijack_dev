# Tado Hijack - Developer Guide

## 🛠️ Development Environment Setup

This guide covers advanced development workflows for contributors and testers working on Tado Hijack.

---

## 🎭 Dummy Simulation Environment

Tado Hijack includes a **Dummy Simulation Environment** that allows you to develop and test features without owning physical Hot Water or Air Conditioning hardware.

### What Are Dummy Zones?

Dummy zones are simulated Tado devices that behave exactly like real hardware but exist entirely in software. They allow you to:

- Test Hot Water (`water_heater`) entity logic without a boiler
- Test Air Conditioning features (fan speed, swing, modes) without AC hardware
- Validate overlay building, pre-API validation, and state management
- Debug complex scenarios without triggering real API calls to physical devices

### Architecture

The dummy system is **fully decoupled** from production code via strategic hooks marked with `[DUMMY_HOOK]` comments:

```
custom_components/tado_hijack/
├── dummy/
│   ├── __init__.py
│   ├── const.py              # Dummy zone IDs
│   └── dummy_handler.py      # Core simulation logic
├── const.py                  # CONF_ENABLE_DUMMY_ZONES toggle
└── coordinator.py            # Injection points marked [DUMMY_HOOK]
```

**Key Design Principles:**
- **Zero Production Impact:** Dummy code is imported but never executed unless explicitly enabled
- **Environment-Based Activation:** Controlled via environment variable, not config UI
- **Clean Separation:** All simulation logic is isolated in the `/dummy` directory
- **Realistic Behavior:** Dummy zones simulate actual Tado API responses and state transitions

### Enabling Dummy Zones

#### Method 1: Environment Variable (Recommended)

Set the environment variable before starting Home Assistant:

```bash
export TADO_ENABLE_DUMMIES=true
python3 -m homeassistant --config /path/to/config
```

#### Method 2: Docker Compose

Add to your `docker-compose.yml`:

```yaml
services:
  homeassistant:
    environment:
      - TADO_ENABLE_DUMMIES=true
```

#### Method 3: Home Assistant Add-on

If running HA as a supervised add-on, modify the add-on environment in the Supervisor UI or add to your add-on configuration.

### What Gets Created

When dummy zones are enabled, the integration will inject:

1. **DUMMY Hot Water (Zone ID: 999998)**
   - Type: `HOT_WATER`
   - Entity: `water_heater.dummy_hot_water`
   - Capabilities: Temperature range 30-65°C
   - Simulated heating power percentage
   - Mock device: `RU01` thermostat

2. **DUMMY Air Conditioning (Zone ID: 999999)**
   - Type: `AIR_CONDITIONING`
   - Entity: `climate.dummy_air_conditioning`
   - Capabilities: Fan speed (AUTO, HIGH, MIDDLE, LOW), Swing (Horizontal/Vertical)
   - Temperature range 16-30°C
   - Modes: COOL, HEAT, DRY, FAN, AUTO
   - Mock device: `VA01` AC controller

### Simulated Behavior

The dummy handler simulates realistic device responses:

#### Hot Water Simulation
- **Power ON:** `heating_power` = 100%
- **Power OFF:** `heating_power` = 0%
- **Temperature Control:** Accepts 30-65°C range
- **Overlay States:** Tracks manual vs auto (schedule) mode

#### AC Simulation
- **Activity Logic:**
  - COOL mode: AC runs if `current_temp > target_temp`
  - HEAT mode: AC runs if `current_temp < target_temp`
  - FAN mode: Always runs when powered ON
  - DRY mode: Runs if `current_temp > target_temp`
- **State Tracking:** Remembers fan speed, swing settings, and mode changes
- **Realistic Sensors:** Simulated inside temperature (24°C) and humidity (60%)

### Testing Workflows

#### Test Hot Water Entity
```yaml
# Turn on hot water with temperature
service: tado_hijack.set_water_heater_mode
data:
  entity_id: water_heater.dummy_hot_water
  operation_mode: heat
  temperature: 55
  overlay: manual
  duration: 30
```

#### Test AC Fan Speed
```yaml
# Set AC fan to HIGH
service: select.select_option
data:
  entity_id: select.dummy_air_conditioning_fan_speed
  option: HIGH
```

#### Test Bulk Operations
```yaml
# Resume all schedules (includes dummy zones)
service: tado_hijack.resume_all_schedules
```

The dummy zones will intercept these commands **before** they reach the API, update their internal state, and reflect changes in Home Assistant instantly.

### API Interception

Dummy zones are **automatically filtered** from real API calls:

- **Overlay Commands:** Intercepted in `dummy_handler.intercept_command()`
- **Resume Schedule:** Filtered in `filter_and_intercept_resume()`
- **Bulk Overlays:** Split via `filter_and_intercept_overlays()`

Real zones proceed to the Tado API normally; dummy zones update locally.

### Development Tips

1. **Forensic Testing:** Use dummy zones to validate new features before testing on real hardware
2. **State Debugging:** Watch `custom_components.tado_hijack` debug logs to see state transitions
3. **Edge Cases:** Test invalid payloads (e.g., `auto` mode with temperature) safely
4. **Concurrency:** Test rapid state changes without wearing out physical valves
5. **Integration Tests:** Validate batching, debouncing, and optimistic updates in isolation

### Disabling Dummy Zones

Simply remove the environment variable and restart Home Assistant. The integration will start normally without any dummy entities.

---

## 🏗️ Local Development Workflow

### Prerequisites

- Python 3.11+
- Home Assistant Core development environment
- Git

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/banter240/tado_hijack.git
   cd tado_hijack
   ```

2. **Symlink to HA config:**
   ```bash
   ln -s $(pwd)/custom_components/tado_hijack ~/.homeassistant/custom_components/
   ```

3. **Enable debug logging** in `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.tado_hijack: debug
   ```

4. **Restart Home Assistant**

### Testing Without Real Hardware

Enable dummy zones as described above, then:

1. Add the Tado Hijack integration via UI
2. Use your real Tado credentials (dummy zones are injected alongside real zones)
3. Test features on `DUMMY Hot Water` and `DUMMY Air Conditioning` entities
4. Validate changes don't affect real zones by checking API call logs

### Code Structure

```
custom_components/tado_hijack/
├── __init__.py              # Integration entry point
├── config_flow.py           # UI configuration flow
├── coordinator.py           # Central coordinator (API orchestration)
├── const.py                 # Constants and configuration
├── diagnostics.py           # Privacy-safe diagnostic reports
├── services.yaml            # Service definitions
│
├── entities/                # Home Assistant entity platforms
│   ├── binary_sensor.py
│   ├── button.py
│   ├── climate.py
│   ├── number.py
│   ├── select.py
│   ├── sensor.py
│   ├── switch.py
│   └── water_heater.py
│
├── helpers/                 # Core business logic
│   ├── api_manager.py       # Command batching & queue
│   ├── auth_manager.py      # OAuth2 token management
│   ├── client.py            # Tado API client wrapper
│   ├── data_manager.py      # JIT polling & cache
│   ├── device_linker.py     # HomeKit device mapping
│   ├── discovery.py         # Zone discovery utilities
│   ├── entity_resolver.py   # HomeKit-to-Zone linking
│   ├── event_handlers.py    # HA state event interception
│   ├── logging_utils.py     # Privacy-safe logging
│   ├── optimistic_manager.py # Instant UI state patching
│   ├── overlay_builder.py   # Overlay payload construction
│   ├── overlay_validator.py # Pre-API validation
│   ├── rate_limit_manager.py # Auto API quota system
│   └── state_memory.py      # RestoreEntity mixin
│
└── dummy/                   # Simulation environment
    ├── const.py             # Dummy zone IDs
    └── dummy_handler.py     # Simulation engine
```

### Key Concepts for Contributors

#### 1. **Coordinator Pattern**
The `TadoDataUpdateCoordinator` is the central orchestrator. All entities reference it via `self.coordinator` to access shared state and trigger API calls.

#### 2. **Optimistic Updates**
The `OptimisticManager` patches local state **immediately** when commands are issued, before the API responds. This provides instant UI feedback.

#### 3. **Command Batching**
The `APIManager` collects commands during a debounce window (default 5s) and fuses them into a single API call.

#### 4. **State Memory**
Entities that inherit from `StateMemoryMixin` automatically save their state to Home Assistant's restoration storage, surviving restarts.

#### 5. **Field Locking**
During overlay commands, "pending" fields are locked to prevent race conditions where concurrent API calls might reset each other.

---

## 🧪 Testing Checklist

Before submitting a PR, validate:

- [ ] Dummy zones function correctly (if feature touches HW/AC)
- [ ] No unintended API calls to real devices during dummy testing
- [ ] Debug logs are privacy-safe (no serials, emails, tokens)
- [ ] Real zones work alongside dummy zones
- [ ] State survives Home Assistant restart (if using StateMemoryMixin)
- [ ] Batching works (multiple changes = 1 API call)
- [ ] Optimistic updates provide instant feedback
- [ ] Pre-validation blocks invalid payloads with clear error messages

---

## 📝 Contributing Guidelines

1. **Use Conventional Commits:** `feat:`, `fix:`, `docs:`, `refactor:`, etc.
2. **Mark Dummy Hooks:** Use `[DUMMY_HOOK]` comments for any dummy-related code
3. **Preserve Privacy:** Never log sensitive data (serials, emails, tokens)
4. **Test with Dummies First:** Validate logic before risking real hardware
5. **Document New Features:** Update README.md and DESIGN.md as needed

---

## 🔍 Debugging Tips

### Enable Verbose Logging
```yaml
logger:
  default: warning
  logs:
    custom_components.tado_hijack: debug
    custom_components.tado_hijack.coordinator: debug
    custom_components.tado_hijack.helpers.api_manager: debug
```

### Watch API Queue
Look for logs like:
```
[APIManager] Queued command: zone_999999 (SET_OVERLAY)
[APIManager] Batching 3 commands into 1 API call
```

### Inspect Dummy Interception
```
[DummyHandler] Intercepted command for dummy zone 999999
[DummyHandler] Updated state: power=ON, mode=COOL, temp=21.0
```

### Check Optimistic State
```
[OptimisticManager] Applied optimistic state: zone_999999, overlay=True, power=ON
```

---

**Happy Hacking! Built for the community — because Tado clearly isn't. 🏴‍☠️**
