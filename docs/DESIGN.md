# Tado Hijack - Architectural Design & Core Concepts

## 🏴‍☠️ Introduction

Tado Hijack is a high-performance, precision-engineered Home Assistant integration designed to bypass the artificial scarcity of the Tado Cloud API. Unlike standard integrations, it treats every API call like gold, utilizing advanced command merging, JIT (Just-In-Time) polling, and HomeKit injection to provide a seamless, local-feeling experience despite cloud limitations.

---

## 🏗️ Core Architecture

### High-Depth System Schematic (The Pipeline)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Home Assistant Ecosystem                           │
│        (Dashboard UI, Automations, Scripts, Third-Party Integrations)       │
└──────┬──────────────────────────────────┬────────────────────────────┬──────┘
       │                                  │                            │
       │ (1) Service Call                 │ (A) Local Interaction      │ (E) State
       ▼ (tado_hijack.set_mode)           ▼ (HomeKit Climate Entity)   ▼ Updates
┌────────────────────────────┐    ┌───────────────────────────┐    ┌──────────┐
│     Tado Hijack Entity     │    │  HomeKit climate Entity   │    │  Other   │
│ (Schedule, HW, AC, Settings)    │ (Temp, HVAC, Modulation)  │    │ Entities │
└──────┬─────────────────────┘    └──────┬────────────────────┘    └────▲─────┘
       │                                 │                              │
       │ (2) Command Dispatch            │ (B) Intercept Event          │
       ▼                                 ▼                              │
┌───────────────────────────────────────────────────────────────────────┼─────┐
│                             Tado Hijack Core                          │     │
│                                                                       │     │
│  ┌───────────────────────┐         ┌──────────────────────────────┐   │     │
│  │   OptimisticManager   │◄──(3)───┤         APIManager           │   │     │
│  │ (UI Instant Patching) │         │ (Debounce, Batching, Jitter) │   │     │
│  └──────────┬────────────┘         └──────────────┬───────────────┘   │     │
│             │                                     │                   │     │
│             │ (4) Update Listeners                │ (5) Put in Queue  │     │
│             └──────────────────┐                  ▼                   │     │
│                                │        ┌───────────────────┐         │     │
│                                └───────►│  API_QUEUE (FIFO) │         │     │
│                                         └─────────┬─────────┘         │     │
│  ┌──────────────────────┐                         │                   │     │
│  │     DataManager      │◄──────────(7)───────────┤ (6) Worker Loop   │     │
│  │ (JIT Poll / Cache)   │                         │   (While True)    │     │
│  └──────────┬───────────┘                         ▼                   │     │
│             │                      ┌──────────────────────────────┐   │     │
│             │ (8) Cache Status     │       RateLimitManager       │   │     │
│             └─────────────────────►│ (Quota Budget, Adaptive Int) │   │     │
│                                    └──────────────┬───────────────┘   │     │
│                                                   │                   │     │
│  ┌──────────────────────┐          ┌──────────────▼───────────────┐   │     │
│  │    EntityResolver    │          │      TadoRequestHandler      │   │     │
│  │ (The Hybrid Linker)  │◄──(9)────┤    (Auth, Response Body)     │   │     │
│  └──────────────────────┘          └──────────────┬───────────────┘   │     │
│                                                   │                   │     │
└───────────────────────────────────────────────────┼───────────────────┼─────┘
                                                    │                   │
                                                    │ (10) HTTPS Call   │ (D) IP Poll
                                                    ▼                   │
┌───────────────────────────┐            ┌──────────────────────────┐   │
│    Tado Internet Bridge   │◄──(11)─────┤      Tado Cloud API      │   │
│ (HomeKit Target Injection)│  Wireless  │    (Restrictive Env)     │   │
└─────────────┬─────────────┘            └──────────────────────────┘   │
              │                                                         │
              │ (C) HomeKit IP Update (Local Feedback Loop)             │
              └─────────────────────────────────────────────────────────┘
```

### The Execution Pipeline Explained

1.  **Command Entry (1 & A):** Commands enter via Hijack services or are intercepted from HomeKit interactions by the `TadoEventHandler`.
2.  **Instant Feedback (3 & 4):** The `APIManager` immediately triggers the `OptimisticManager` to patch the UI. Listeners are updated instantly—no "loading" spinner.
3.  **The Debounce Window:** Commands for the same zone are held for `debounce_time` (Default 5s) to allow for **Deep Command Fusion** (Batching).
4.  **The Worker Loop (6):** A background `while True` loop waits for the `API_QUEUE`. Once data arrives, it gathers all pending commands into a single **Batch**.
5.  **Quota Guard (7):** Before execution, the `RateLimitManager` verifies the daily budget and calculates the optimal adaptive interval.
6.  **Cloud Sync (10):** The `TadoRequestHandler` executes the batched HTTPS call, capturing detailed error bodies if the API rejects the request.
7.  **The HomeKit Loop (C & D):** The Bridge receives the command and updates its internal state. Home Assistant's native HomeKit integration then polls the Bridge via **Local IP**, completing the feedback loop and reflecting the final state in the climate entity (D & E).

The integration is built on a modular, helper-centric architecture that separates logic into specialized managers.

### 🧩 Specialized Managers

| Component | Responsibility |
| :--- | :--- |
| **`DataManager`** | High-precision JIT poll planning. Decides *exactly* when to fetch data based on usage and expiration. |
| **`APIManager`** | Central queue for all API writes. Handles batching, sequencing, and jitter. |
| **`RateLimitManager`** | Real-time quota tracking. Manages the "API Gold" budget and adaptive intervals. |
| **`OptimisticManager`** | UI instant-feedback engine. Patches local state immediately after a command without waiting for a poll. |
| **`EntityResolver`** | The "Missing Link" engine. Automatically maps HomeKit climate entities to Tado logical zones. |

---

## 🧠 Strategic Concepts

### 1. Extreme Batching (Command Fusion)
Instead of sending 10 requests for 10 rooms, Tado Hijack buffers commands during a configurable **Debounce Window**.
- **The Result:** 10 zone changes = **1 API Call**.
- **Scope:** Applies to `set_mode`, `set_water_heater_mode`, and all bulk buttons.

### 2. JIT (Just-In-Time) Polling
We don't poll on a fixed timer if it's not needed.
- **Dynamic Intervals:** Polling speed adapts to your daily quota and current activity.
- **Event-Driven:** Hardware metadata (Firmware, Battery) is only fetched every 24h or on demand.
- **Dirty Flags:** Cache segments (Offsets, Away Config) are only refreshed if they are marked "dirty" and a user requests them.

### 3. The "API Gold" Budget (Auto Quota)

The integration uses a **Weighted Predictive Model** to distribute calls intelligently across the day.

#### Quota Distribution Schematic

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TADO DAILY API LIMIT (100%)                        │
│             (e.g., 5000 calls/day or the new 100 calls/day limit)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ (1) DEDUCT FIXED RESERVES                                                   │
│ ┌───────────────────────────┐   ┌───────────────────────────┐               │
│ │   Background Syncs (24h)  │   │   External User Excess    │               │
│ │ (Hardware, Metadata, Bat) │ + │(Official App, Automations)│               │
│ └───────────────────────────┘   └───────────────────────────┘               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ (2) CALCULATE FREE BUDGET                                                   │
│ FREE_BUDGET = (Limit - Reserves) * auto_api_quota_percent (e.g. 80%)        │
└──────┬───────────────────────────────────────────────────────────────┬──────┘
       │                                                               │
       ▼ (Day Phase: PERFORMANCE)                                      ▼ (Night: ECONOMY)
┌──────────────────────────────────────┐               ┌──────────────────────┐
│  High-Speed Polling Window           │               │  Sleep Polling Window│
│  (e.g., 07:01 - 21:59)               │               │  (e.g., 22:00-07:00) │
│                                      │               │                      │
│  ┌────────────────────────┐          │               │  ┌────────────────┐  │
│  │ REINVESTED SAVINGS     │◄─────────┼──(Reinvest)───┤  │ SAVINGS BANK   │  │
│  │ (From Economy Window)  │          │               │  │ (0 or Low Poll)│  │
│  └──────────┬─────────────┘          │               │  └────────────────┘  │
│             │                        │               │                      │
│             ▼                        │               ▼                      │
│  FINAL ADAPTIVE INTERVAL             │        REDUCED POLLING INTERVAL      │
│  (Target: ~45s - 300s)               │        (Target: ~1h or Paused)       │
└──────────────────────────────────────┘               └──────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ (3) TIME SYNC (Berlin 12:01 AM)                                             │
│ Quota resets exactly at 12:01 AM Europe/Berlin. The model continuously      │
│ recalculates the interval based on seconds_until_reset to prevent a crash.  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Economy Window:** Automatically slows down polling during your sleep window (e.g., 22:00 - 07:00).
- **Performance Reinvestment:** Saved calls from the night are reinvested into faster updates during the day.
- **Berlin-Sync:** Precision tracking against Tado's hard-coded reset time (**12:01 AM Europe/Berlin**).

### 4. Safety Floors & Adaptive Behavior

To protect your Tado account from automated detection and "Account Locks", the integration enforces hard-coded minimum intervals:

- **🛡️ Standard Cloud:** Minimum **45 seconds** per update.
- **🛡️ API Proxy:** Minimum **120 seconds** per update (Conservative floor required for stable proxy operation).

*Note: These limits apply even if your daily budget allows for higher frequencies. Continuity and account safety always take precedence over speed.*

### 5. HomeKit Injection
This is our unique hybrid approach.
- **HomeKit:** Handles the core climate entity (Local, reliable, zero cost).
- **Hijack:** Injects missing cloud features (Schedules, Child Lock, Hot Water, AC Modes) into the *same* device.
- **Result:** You get a single, unified device in Home Assistant that is both local-first and feature-complete.

---

## 🚿 Service Logic & Validation

All control paths are protected by a **Fail-Fast Validation Layer**.

### Service: `set_mode` / `set_water_heater_mode`
- **`hvac_mode / operation_mode`:**
  - `auto`: Resumes the Tado Smart Schedule.
  - `heat`: Activates a manual overlay.
  - `off`: Turns the zone off.
- **`overlay` types:**
  - `manual`: Indefinite override (stays until you change it).
  - `next_block`: Automatically returns to schedule at the next Tado time block.
  - `presence`: Stays active until your Home/Away presence changes.
- **`duration`:** Optional timer in minutes for `manual` overlays.

### Automatic Post-Action Polling (`refresh_after`)
The integration intelligently decides if a confirmatory poll is necessary:
- **Instant:** For `auto` (Resume) or permanent changes.
- **Deferred:** For timed modes, the refresh is scheduled for the *end* of the timer to save quota.

---

## 🛡️ Security & Privacy

- **Redaction:** Diagnostics and logs undergo multi-layer Regex masking (Serials, Emails, Tokens).
- **Race-Condition Protection:** API writes are strictly queued and executed sequentially.
- **Local Resilience:** Core heating control remains functional via HomeKit even if Tado servers are down.

---

## 🔓 Rate Limit Bypass (API Proxy)

For power users, Tado Hijack supports a local **API Proxy** to further decouple the integration from cloud-side constraints.

### Proxy Integration Schematic

```text
┌───────────────────────────┐          ┌───────────────────────────────────┐
│       Tado Hijack         │          │          Local API Proxy          │
│    (Home Assistant)       │          │     (e.g., Docker Container)      │
└─────────────┬─────────────┘          └──────────────────┬────────────────┘
              │                                           │
              │ (1) Request (No Auth)                     │ (2) Auth Injection
              ├──────────────────────────────────────────►│ (Local Secrets)
              │                                           │
              │                                           ▼
              │                        ┌───────────────────────────────────┐
              │                        │        Tado Cloud API             │
              │                        │ (Status: 100/day hard limit)      │
              │                        └──────────────────┬────────────────┘
              │                                           │
              │ (4) Return Cached/Real                    │ (3) Response
              │◄──────────────────────────────────────────┤
              │                                           │
└─────────────┴─────────────┘          └──────────────────┴────────────────┘
```

### Quota Scalability Comparison

Tado is actively choking the standard API. Tado Hijack is engineered to handle this **without any user intervention**, but the Proxy Bypass offers a significant boost for power users.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      QUOTA SCALABILITY COMPARISON                           │
└─────────────────────────────────────────────────────────────────────────────┘
         DIRECT CLOUD ACCESS                      LOCAL PROXY BYPASS
 ┌────────────────────────────────┐        ┌──────────────────────────────────┐
 │ Tado Cloud API (Single Acc)    │        │ Multi-Account Proxy Cluster      │
 ├────────────────────────────────┤        ├──────────────────────────────────┤
 │ Current: ~5000 calls / day     │        │ 3000 calls / account / day       │
 │ Future:  ~100 calls / day      │        │ Scalable: N x 3000 calls / day   │
 └──────────────┬─────────────────┘        └───────────────┬──────────────────┘
                │                                          │
                ▼                                          ▼
      [ ADAPTIVE SURVIVAL ]                       [ TOTAL FREEDOM ]
 System automatically slows down.          High-frequency polling (120s).
 CONTINUITY is guaranteed.                 Unlimited bandwidth for automation.
```

### Strategic Benefits of the Proxy

1.  **Auth Outsourcing:** The proxy handles OAuth2 token management and refreshes internally. Hijack simply sends requests to the local proxy URL.
2.  **Pattern Obfuscation:** The proxy allows for advanced **Multi-Level Jitter**, breaking the temporal correlation between Home Assistant actions and Tado cloud logs.
3.  **Local Cache Layer:** Frequently requested data can be served directly from the proxy's local memory, saving precious API calls for critical commands.
4.  **Bypass Throttling:** By presenting a stable, single-IP endpoint to Tado, the proxy mitigates common "Account Lock" scenarios triggered by multiple rapid connections from different HA components.
5.  **Multi-Account Scaling:** While a single cloud account is doomed to the 100-call wall, the proxy can orchestrate multiple accounts to pool their quota, effectively providing unlimited bandwidth.
6.  **Performance Boost:** While the Direct Cloud mode must adaptively slow down to survive the 100-call limit, the Proxy mode allows for consistent, high-speed updates (45s - 120s) regardless of daily usage.

---

**Built for the community — because Tado clearly isn't.**
