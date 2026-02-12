# Qvantum Heat Pump Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/majorfrog/qvantum-hass?style=flat-square)](https://github.com/majorfrog/qvantum-hass/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Home Assistant integration for Qvantum heat pumps, providing real-time monitoring and control through the Qvantum cloud API.

> **Disclaimer**: This is an unofficial integration and is not affiliated with or endorsed by Qvantum AB. Use at your own risk.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Services](#services)
- [Automation Examples](#automation-examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Features

### Comprehensive Device Monitoring

**Sensors (100+ entities)**

- **Temperature Monitoring**: Indoor, outdoor, flow temperatures, tank temperature, and 30+ internal temperature sensors (BT1-BT34)
- **Performance Metrics**: Compressor speed, pump speeds, flow rates, pressures
- **Energy Monitoring**: Total power, compressor energy, additional energy consumption with historical tracking
- **System Status**: Heat pump operating status, operating mode, connectivity
- **Diagnostic Data**: Firmware versions, uptime, system parameters

**Binary Sensors**

- Real-time connectivity status with disconnect reason tracking
- Active alarm detection and monitoring
- Service access status indicator
- Relay states for heating, valves, and additional components
- SmartControl status indicators

### Device Control

**Number Controls**

- Indoor temperature target configuration
- DHW (Domestic Hot Water) start/stop temperature settings
- DHW capacity target adjustment
- Advanced heating parameters

**Select Entities**

- Heating curve shift (room temperature offset, -9 to +9)
- SmartControl mode selection (Off, Eco, Balanced, Comfort)
- Operation mode control (Auto, Manual, Additional Heat Only)
- DHW priority time configuration
- DHW outlet temperature selection
- Tap water capacity targets
- Room compensation factor

**Switch Controls**

- Extra hot water boost mode (1-hour quick activation)
- SmartControl enable/disable for heating and DHW
- Manual operation mode controls (Heating, DHW, Addition)
- Vacation mode
- Auto-elevate access control
- Various system settings

**Button Controls**

- Extra hot water activation (1 hour)
- Manual sensor refresh
- Service technician access elevation

### Advanced Features

- **Multi-Device Support**: Manage multiple heat pumps on one account
- **Alarm Monitoring**: Real-time alarm detection with severity levels and detailed descriptions
- **Access Management**: Automatic elevation to service technician level for advanced settings
- **Dual-Speed Polling**:
  - Fast 5-second updates for power/current sensors (real-time energy monitoring)
  - Normal 30-second updates for temperature/status sensors (efficient polling)
- **Automatic Token Refresh**: Seamless authentication without interruption
- **Availability Tracking**: Entities automatically reflect device online/offline status
- **Multi-Language Support**: English and Swedish translations included

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. In Home Assistant, go to **HACS** → **Integrations**
3. Click the **⋮** menu in the top right corner and select **Custom repositories**
4. Add this repository URL: `https://github.com/majorfrog/qvantum-hass`
5. Select **Integration** as the category
6. Click **Add**
7. Click **Download** on the Qvantum Heat Pump integration
8. Restart Home Assistant
9. Go to **Settings** → **Devices & Services**
10. Click **+ Add Integration**
11. Search for "Qvantum Heat Pump"
12. Follow the configuration steps

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/majorfrog/qvantum-hass/releases)
2. Extract the `qvantum_hass` folder from the archive
3. Copy the folder to your Home Assistant's `custom_components` directory
   - Path should be: `<config_dir>/custom_components/qvantum_hass/`
4. Restart Home Assistant
5. Go to **Settings** → **Devices & Services**
6. Click **+ Add Integration**
7. Search for "Qvantum Heat Pump"
8. Follow the configuration steps

## Configuration

### Initial Setup

1. After adding the integration, you'll be prompted for your Qvantum account credentials:
   - **Email**: Your Qvantum account email address
   - **Password**: Your Qvantum account password

2. Click **Submit**

3. The integration will:
   - Authenticate with the Qvantum cloud service
   - Discover all heat pumps on your account
   - Create devices and entities for each heat pump

### Options

After setup, you can configure polling intervals:

1. Go to **Settings** → **Devices & Services**
2. Find the Qvantum Heat Pump integration
3. Click **Configure**
4. Adjust settings:
   - **Normal Scan Interval**: How often to poll for temperature/status data (10-300 seconds, default: 30)
   - **Fast Scan Interval**: How often to poll for power/current data (5-60 seconds, default: 5)

> **Note**: The integration uses two separate polling intervals for optimal performance:
>
> - **Fast polling (5s)**: For power consumption and current sensors - provides real-time energy monitoring
> - **Normal polling (30s)**: For temperature and status sensors - reduces unnecessary API load
>
> Lower intervals provide more responsive data but may impact API rate limits and system performance.

## Entities

The integration creates comprehensive entities for each heat pump device. Most advanced/diagnostic entities are disabled by default and can be enabled as needed.

### Sensors

**Enabled by Default:**

- Outdoor Temperature (BT1)
- Accumulator Tank Temperature (BT30)
- Heating Medium Flow Line (BT11)
- Heat Pump Status
- Operation Mode
- Total Power
- Compressor Energy
- Additional Energy
- DHW Capacity
- Alarm Count
- Active Alarms
- Device Uptime
- Firmware Versions

**Disabled by Default (can be enabled in UI):**

- All internal temperature sensors (BT2-BT34)
- Pressure sensors (BP1, BP2)
- Flow rate sensors
- Fan and pump speeds
- Compressor speed
- Valve positions
- Advanced calculated values

### Controls

**Number Entities:**

- Indoor Temperature Target
- DHW Start/Stop Temperatures
- DHW Capacity Target

**Select Entities:**

- Heating Curve Shift (enabled by default, -9 to +9)
- SmartControl Mode
- Operation Mode
- DHW Priority Time
- DHW Outlet Temperature
- Tap Water Capacity Target
- Room Compensation Factor
- Sensor Mode (which temperature sensor controls operation: BT2, BT3, BTX, or Off)

**Switch Entities:**

- Extra Hot Water (enabled by default)
- SmartControl Heating
- SmartControl DHW
- Manual Operation Modes
- Vacation Mode (enabled by default)
- Auto-Elevate Access
- Various system settings (disabled by default)

**Button Entities:**

- Refresh Sensors
- Extra Hot Water 1 Hour
- Elevate Access Level

## Services

### Activate Extra Hot Water

Activate extra hot water mode for a specified duration (1-24 hours).

**Service:** `qvantum.activate_extra_hot_water`

**Parameters:**

- `device_id`: Your Qvantum device ID (required)
- `duration`: Duration in hours, 1-24 (required)

**Examples:**

```yaml
# Automation example - activate for 2 hours
service: qvantum.activate_extra_hot_water
data:
  device_id: "your_device_id_here"
  duration: 2

# Script for 3 hour boost
activate_hot_water_3h:
  alias: "Extended Hot Water Boost"
  sequence:
    - service: qvantum.activate_extra_hot_water
      data:
        device_id: "your_device_id_here"
        duration: 3
```

### Cancel Extra Hot Water

Cancel active extra hot water mode.

**Service:** `qvantum.cancel_extra_hot_water`

**Parameters:**

- `device_id`: Your Qvantum device ID (required)

**Example:**

```yaml
service: qvantum.cancel_extra_hot_water
data:
  device_id: "your_device_id_here"
```

**Note:** You can also use the Extra Hot Water switch entity to turn on (1 hour) or turn off the boost mode.

## Automation Examples

### Monitor Alarms

#### Notify on Critical Heat Pump Alarms

Get notified immediately when a critical or severe alarm occurs:

```yaml
automation:
  - alias: "Notify on Critical Heat Pump Alarm"
    description: "Send notification when heat pump has critical/severe alarms"
    trigger:
      - platform: state
        entity_id: binary_sensor.alarm_state
        to: "on"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('binary_sensor.alarm_state', 'most_severe_severity')
             in ['CRITICAL', 'SEVERE'] }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🚨 Heat Pump Alarm!"
          message: >
            Severity: {{ state_attr('binary_sensor.alarm_state', 'most_severe_severity') }}
            {{ state_attr('binary_sensor.alarm_state', 'most_severe_description') }}
          data:
            priority: high
            ttl: 0
```

#### Send Alarm Summary

Get a daily summary of any alarms that occurred:

```yaml
automation:
  - alias: "Daily Heat Pump Alarm Summary"
    description: "Send daily alarm summary if any alarms occurred"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: numeric_state
        entity_id: sensor.alarm_count
        above: 0
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Heat Pump Daily Summary"
          message: >
            Active alarms: {{ states('sensor.active_alarms') }}
            Total alarm count: {{ state_attr('sensor.alarm_count', 'total_alarms') }}
```

### Monitor Connectivity

#### Alert When Heat Pump Goes Offline

Get notified if your heat pump loses connection:

```yaml
automation:
  - alias: "Heat Pump Offline Alert"
    description: "Alert when heat pump disconnects from cloud"
    trigger:
      - platform: state
        entity_id: binary_sensor.connectivity
        to: "off"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Heat Pump Offline"
          message: >
            Heat pump disconnected at {{ state_attr('binary_sensor.connectivity', 'timestamp') }}
            Reason: {{ state_attr('binary_sensor.connectivity', 'disconnect_reason') }}
```

#### Notify When Back Online

Get a confirmation when connectivity is restored:

```yaml
automation:
  - alias: "Heat Pump Back Online"
    description: "Notify when heat pump reconnects"
    trigger:
      - platform: state
        entity_id: binary_sensor.connectivity
        to: "on"
    condition:
      - condition: state
        entity_id: binary_sensor.connectivity
        state: "off"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "✅ Heat Pump Online"
          message: "Heat pump has reconnected to the cloud"
```

### Smart Hot Water Management

#### Auto-activate Hot Water Before Shower Time

Automatically boost hot water before typical shower times:

```yaml
automation:
  - alias: "Morning Hot Water Boost"
    description: "Activate extra hot water before morning showers"
    trigger:
      - platform: time
        at: "06:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.connectivity
        state: "on"
    action:
      - service: qvantum.activate_extra_hot_water
        data:
          device_id: "your_device_id_here"
          duration: 2
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Active internet connection
- Qvantum account with registered heat pump

## Installation

### HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Click on HACS in the sidebar
   - Click on "Integrations"
   - Click the three dots in the top right corner
   - Select "Custom repositories"
   - Add `https://github.com/majorfrog/qvantum-hass`
   - Select "Integration" as the category
3. Click "Install"
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/majorfrog/qvantum-hass/releases)
2. Extract the ZIP file
3. Copy the `qvantum_hass` folder to your Home Assistant's `custom_components/` directory (inside your config folder)
   - Path should be: `<config_dir>/custom_components/qvantum_hass/`
4. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Qvantum"
4. Enter your Qvantum account credentials:
   - **Email**: Your Qvantum account email
   - **Password**: Your Qvantum account password

The integration will automatically discover all heat pumps associated with your account.

### Finding Your Device ID

To use the services (like activating extra hot water), you'll need your device ID. You can find it in:

- The entity IDs: `sensor.qvantum_heat_pump_<device_id>_*`
- Developer Tools → States → look for any qvantum entity and check the device ID in the entity_id

## Available Entities

Once configured, the integration will create the following types of entities for each heat pump:

### Standard Metrics (from Public API)

- Outdoor Temperature
- Indoor Temperature
- Heating Flow Temperature
- Heating Flow Temperature Target
- Tap Water Tank Temperature
- Tap Water Capacity
- DHW Start/Stop Temperatures
- Total Energy
- Compressor Energy
- Additional Energy

### Extended Internal Metrics

- **Temperature Sensors**: BT1-BT34 (various temperature points)
- **Pressure Sensors**: BP1-BP2 (low and high pressure)
- **Flow Sensors**: BF1 (DHW flow rate)
- **Speed Controls**: Compressor speed, pump speeds, fan speed
- **Relay States**: Additional heating relays (L1-L3), diverting valves
- **Position Sensors**: Shunt valve position

### Device Information

- Connectivity Status
- Service Access Status
- Display Firmware Version
- Control Circuit Firmware Version
- Inverter Firmware Version
- Device Uptime

### Controllable Settings

All numeric and boolean settings exposed by the Qvantum API can be controlled through Home Assistant, including:

- Indoor temperature target
- Heating curve shift (indoor temperature offset)
- DHW capacity target
- DHW start/stop temperatures
- Various mode switches

## Data Update

The integration polls the Qvantum API every 30 seconds by default to update all entity states. This interval is optimized to balance between having up-to-date information and not overloading the API.

## Troubleshooting

### Integration Won't Load

**Symptoms**: Integration fails to set up or shows error during configuration

**Solutions**:

1. Verify your Qvantum credentials are correct
2. Test by logging into the [Qvantum web portal](https://app.qvantum.com) with the same credentials
3. Check Home Assistant logs: **Settings** → **System** → **Logs**
4. Ensure you have an active internet connection
5. Try removing and re-adding the integration

**Common Errors**:

- `cannot_connect`: API is unreachable - check your internet connection
- `invalid_auth`: Incorrect email or password
- `no_devices`: Account has no registered heat pumps

### Entities Show as "Unavailable"

**Symptoms**: Most or all entities show "Unavailable"

**Solutions**:

1. Check the **Connectivity** binary sensor - heat pump must be online
2. Verify device has internet connection
3. Check if Qvantum cloud service is operational
4. Wait a few minutes - may be temporary connectivity issue
5. Try clicking the **Refresh Sensors** button
6. Restart the integration: **Settings** → **Devices & Services** → Qvantum → **⋮** → **Reload**

### Setting Changes Don't Apply

**Symptoms**: Changes to number/select/switch entities don't affect the heat pump

**Solutions**:

1. Verify heat pump is online (check connectivity sensor)
2. Check you have proper access level - some settings require service technician access
3. Enable **Auto-Elevate Access** switch for advanced settings
4. Wait 30-60 seconds for changes to propagate
5. Check Home Assistant logs for permission errors
6. Try using the **Elevate Access Level** button before changing settings

### Missing Entities

**Symptoms**: Expected entities don't appear

**Solutions**:

1. Many advanced entities are disabled by default
2. Go to **Settings** → **Devices & Services** → Qvantum → **Device**
3. Click on the device name
4. Scroll through entity list and enable desired entities
5. Commonly disabled entities: internal temperature sensors (BT2-BT34), pressure sensors, advanced diagnostics

### High CPU Usage or Slow Updates

**Symptoms**: Home Assistant becomes slow after adding integration

**Solutions**:

1. Increase the scan interval: **Settings** → **Devices & Services** → Qvantum → **Configure**
2. Recommended minimum: 30 seconds (default)
3. Disable unused entities to reduce processing load
4. Check for errors in logs that might cause excessive retries

### Debug Logging

Enable detailed logging for troubleshooting:

```yaml
logger:
  default: info
  logs:
    custom_components.qvantum_hass: debug
```

Then check logs at: **Settings** → **System** → **Logs**

### API Rate Limiting

The integration is configured to be respectful of API limits:

- Dual-speed polling:
  - Fast coordinator: 5-second updates for 6 power/current metrics only
  - Normal coordinator: 30-second updates for all other sensors
- Automatic token refresh
- Intelligent error handling and backoff
- Inventory caching to reduce API calls
- Minimal API load compared to single-interval polling

If you experience rate limiting:

1. Increase the normal scan interval to 60+ seconds (Settings → Configure)
2. Increase the fast scan interval to 10-15 seconds if not monitoring real-time power
3. Reduce number of enabled entities
4. Check logs for excessive API calls

### Getting Help

If you continue to experience issues:

1. **Check existing issues**: [GitHub Issues](https://github.com/majorfrog/qvantum-hass/issues)
2. **Create a new issue** with:
   - Home Assistant version
   - Integration version
   - Device model
   - Detailed description of the problem
   - Relevant log entries (with sensitive data removed)
   - Steps to reproduce

## Support and Community

For issues, questions, or feature requests:

- **Issues**: [GitHub Issue Tracker](https://github.com/majorfrog/qvantum-hass/issues)
- **Discussions**: Use GitHub Discussions for questions and community support
- **Home Assistant Community**: [Home Assistant Forums](https://community.home-assistant.io/)

## Contributing

Contributions are welcome! Whether it's bug reports, feature requests, or code contributions, please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Ways to contribute:

- Report bugs and suggest features
- Improve documentation
- Submit pull requests
- Help others in discussions
- Share your automations and use cases

## Credits and Acknowledgments

This integration was developed independently and is inspired by the Qvantum ecosystem. Special thanks to:

- The Home Assistant community for their excellent documentation and support
- Contributors and testers who helped improve this integration

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

**Important**: This is an unofficial, community-developed integration and is not affiliated with, endorsed by, or supported by Qvantum AB.

- Use at your own risk
- The integration uses Qvantum's cloud API which may change without notice
- Please refer to Qvantum's terms of service regarding API usage
- The developers of this integration are not responsible for any issues arising from its use
- Always ensure you understand the impact of changing heat pump settings before doing so

## Privacy and Security

This integration:

- Stores your Qvantum credentials locally in Home Assistant
- Communicates directly with Qvantum's cloud API
- Does not send data to any third parties
- Uses HTTPS for all API communications
- Implements automatic token refresh to maintain security

Your credentials are stored securely in Home Assistant's configuration and are never logged or transmitted except to Qvantum's official API servers.
