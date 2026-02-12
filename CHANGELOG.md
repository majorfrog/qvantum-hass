# Changelog

All notable changes to the Qvantum Heat Pump integration for Home Assistant will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2026-02-12

### Changed

- **Manual mode**: Converted from switch to select entity with three options: Off, Heating, and Cooling (was previously a simple on/off switch)
- **Guide heating**: Renamed to "Heat emitter type" and converted to enum sensor with translated states (Underfloor heating / Radiators)
- **Tap water capacity target**: Now displays proper grammar with "1 person", "2 persons", etc. instead of raw numbers

### Added

- **BTX configuration sensor**: Read-only diagnostic enum sensor showing BTX input configuration (Undefined NTC 10k, Pool NTC 10k, SG Ready A)
- **BT4 configuration sensor**: Read-only diagnostic enum sensor showing BT4 input configuration (Undefined NTC 10k, SG Ready B)
- **Vacation start sensor**: Timestamp sensor showing when vacation mode starts
- **Vacation stop sensor**: Timestamp sensor showing when vacation mode ends
- **Wi-Fi SSID sensor**: Diagnostic text sensor showing the connected Wi-Fi network name
- **English translations**: Added missing English translation file (en.json) to ensure proper entity naming in English-language installations

### Fixed

- **DHW mode select**: Fixed blocking API call that could freeze the event loop (now uses `async_add_executor_job`)
- **Operation mode select**: Fixed same blocking API call issue as DHW mode
- **Entity naming**: Fixed issue where entities would show as "none" or incomplete names in English installations due to missing translation file

## [1.0.0] - 2026-01-30

### Added

#### Core Features

- Initial release of the Qvantum Heat Pump integration for Home Assistant
- Configuration flow for easy setup via UI
- Options flow for configuring scan intervals:
  - Normal scan interval: 10-300 seconds (default 30s) for temperature/status sensors
  - Fast scan interval: 5-60 seconds (default 5s) for power/current sensors
- Dual-coordinator architecture for optimized polling performance
- Multi-device support: manage multiple heat pumps per account
- Automatic device discovery on account
- Automatic authentication token refresh
- Multi-language support (English and Swedish)

#### Sensors

- **Temperature Sensors**: 30+ temperature sensors (BT1-BT34) including outdoor, indoor, flow, and tank temperatures
- **Energy Monitoring**: Total power, compressor energy, and additional energy consumption sensors with fast 5-second updates for real-time monitoring
- **Performance Metrics**: Compressor speed, pump speeds, fan speed, flow rate
- **System Status**: Heat pump status, operation mode, connectivity state
- **Device Information**: Firmware versions (display, CC, inverter), uptime
- **Alarm Monitoring**: Alarm count sensor and detailed active alarms sensor with severity levels

#### High-Frequency Power Monitoring

- Fast polling (5-second updates) for:
  - Total power consumption (W)
  - Heating power (W)
  - DHW power (W)
  - Input current L1, L2, L3 (A)
- Enables real-time energy monitoring without excessive API load on temperature sensors

#### Binary Sensors

- Device connectivity status with disconnect reason tracking
- Alarm state indicator
- Service access status
- Relay states: additional heating relays, diverting valves
- SmartControl status indicators

#### Controls

- **Number Entities**: Indoor temperature target, DHW capacity target, DHW start/stop temperatures
- **Select Entities**: Heating curve shift (indoor temperature offset, -9 to +9), SmartControl mode, operation mode, DHW priority time, DHW outlet temperature, tap water capacity, room compensation factor
- **Switch Entities**: Extra hot water, SmartControl heating/DHW, manual operation modes, vacation mode, auto-elevate access
- **Button Entities**: Refresh sensors, extra hot water activation, elevate access level

#### Services

- `qvantum_hass.activate_extra_hot_water`: Activate extra hot water for 1-24 hours
- `qvantum_hass.cancel_extra_hot_water`: Cancel active extra hot water mode

#### Advanced Features

- Auto-elevate access feature for reading advanced settings requiring service technician access
- Persistent storage of auto-elevate state across restarts
- Connectivity-based entity availability tracking
- Intelligent entity categorization (diagnostic vs config vs main)
- Smart default entity enabling (common entities enabled, advanced disabled)
- Comprehensive error handling and logging

### Technical Details

- Polling interval: Configurable (default 30 seconds)
- API communication: Synchronous API calls in executor threads
- Authentication: Firebase Authentication with automatic token refresh
- Data coordinator pattern for efficient updates
- Device info with proper identifiers, manufacturer, model, and serial number
- Proper device classes and units of measurement for all sensors

### Fixed

- N/A (initial release)

### Security

- Secure storage of credentials via Home Assistant config entries
- Automatic token refresh to minimize credential exposure

## Migration from qvantum2mqtt

This integration replaces the qvantum2mqtt project with the following improvements:

- No MQTT broker required
- Native Home Assistant integration
- UI-based configuration
- Automatic device discovery
- All entities from qvantum2mqtt are supported
- Better entity organization and naming
- Proper device classes and units

See ENTITY_MAPPING.md for detailed entity mapping information.
