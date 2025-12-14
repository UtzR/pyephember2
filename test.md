# test.py - EPH Controls Ember Debug & Development Tool

A comprehensive command-line tool for interacting with EPH Controls Ember heating systems. This tool is designed for debugging, development, and testing of the pyephember2 library.

## Features

- **Interactive CLI** - Command-line interface for real-time control
- **Dual Transport** - Send commands via MQTT or HTTP
- **Live MQTT Updates** - Subscribe to real-time device updates
- **Comprehensive Logging** - All HTTP and MQTT communication logged to files
- **Zone Control** - Turn zones on/off, set temperatures, activate boost
- **Status Display** - View current temperatures, modes, and schedules

## Requirements

- Python 3.11+
- pyephember2 library (local)
- paho-mqtt
- requests

## Usage

### Basic Usage

```bash
python test.py --email your@email.com
```

You will be prompted for your password (input is hidden).

### With Password

```bash
python test.py --email your@email.com --password "yourpassword"
```

### With Debug Output

```bash
# Info-level logging
python test.py --email your@email.com -d

# Full debug logging (HTTP + MQTT details)
python test.py --email your@email.com -dd
```

### Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `--email` | EPH account email address (required) |
| `--password` | Account password (will prompt if not provided) |
| `-d`, `--debug` | Enable debug output (use twice for verbose) |
| `--http-debug` | Show raw HTTP requests/responses in console |
| `--full-raw` | Show full raw JSON without truncation |
| `--zone` | Focus on a specific zone during startup |
| `--json` | Output raw JSON and exit (for scripting) |

## Interactive Commands

After startup, the program enters interactive mode with the following commands:

### General Commands

| Command | Description |
|---------|-------------|
| `help` | Display all available commands |
| `zones` | List all available zone names |
| `refresh` | Refresh zone data from HTTP API |
| `exit` / `quit` | Exit the program |

### Zone Status

| Command | Description |
|---------|-------------|
| `status <zone>` | Show current status (temp, mode, boost) |
| `schedule <zone>` | Show the zone's heating schedule |

### Zone Control

| Command | Description |
|---------|-------------|
| `on <zone>` | Turn a zone ON |
| `off <zone>` | Turn a zone OFF |
| `temp <zone> <temperature>` | Set target temperature (e.g., `temp Living Room 21.5`) |
| `boost <zone> [hours]` | Activate boost (default: 1 hour, use 0 to cancel) |

### Transport Mode

| Command | Description |
|---------|-------------|
| `mode` | Show current transport mode |
| `mode mqtt` | Switch to MQTT transport |
| `mode http` | Switch to HTTP transport |

### MQTT Commands

| Command | Description |
|---------|-------------|
| `mqtt status` | Show MQTT connection status |
| `mqtt start` | Start MQTT listener for real-time updates |
| `mqtt stop` | Stop MQTT listener |

## Examples

### Basic Session

```
$ python test.py --email user@example.com
Password: ********

============================================================
  Connecting to EPH Controls Ember
============================================================
  Email: user@example.com
  ...
  ✓ Login successful

============================================================
  Interactive Mode
============================================================
  Type 'help' for available commands, 'exit' to quit.

eph[mqtt]> zones
  Available zones:
    - Living Room
    - Bedroom
    - Hot Water

eph[mqtt]> status Living Room
  Living Room (HTTP cache)
  Is Hot Water:  False
  Current Temp:  19.5°C
  Target Temp:   20.0°C
  Mode:          AUTO (0)
  Boost Active:  No
  Boost Hours:   0
```

### Using MQTT for Real-Time Updates

```
eph[mqtt]> mqtt start
  ✓ MQTT listener started, subscribed to 3 zone(s)

eph[mqtt]> off Living Room
  Turning off Living Room via MQTT...
  ✓ Zone turned OFF

  [MQTT] Received update for MAC 10ba77692:
    PointIndex 7 (MODE): 3
    ...

eph[mqtt]> status Living Room
  Living Room (MQTT: 2025-12-14T19:09:30.497386)
  ...
  Mode:          OFF (3)
```

### Setting Temperature

```
eph[mqtt]> temp Bedroom 21.5
  Setting Bedroom to 21.5°C via MQTT...
  ✓ Temperature set to 21.5°C
```

### Boost Control

```
# Activate 2-hour boost
eph[mqtt]> boost Living Room 2
  Boosting Living Room for 2 hour(s) via MQTT...
  ✓ Boost activated for 2h

# Cancel boost
eph[mqtt]> boost Living Room 0
  Cancelling boost for Living Room via MQTT...
  ✓ Boost cancelled
```

## Log Files

The program creates two log files in the current directory:

### test_log_http

Contains all HTTP API communication:

```
# HTTP Communication Log
# Started: 2025-12-14T18:00:00.000000
======================================================================

======================================================================
>>> SENDING REQUEST [2025-12-14T18:00:01.123456]
======================================================================
Method: POST
Endpoint: appLogin/login
Send Token: False
Timeout: 10
Data:
{
  "userName": "user@example.com",
  "password": "***"
}

----------------------------------------------------------------------
<<< RECEIVED RESPONSE [2025-12-14T18:00:02.234567]
----------------------------------------------------------------------
Status Code: 200
Body:
{
  "status": 0,
  "data": { ... }
}
```

### test_log_mqtt

Contains all MQTT communication:

```
# MQTT Communication Log
# Started: 2025-12-14T18:00:00.000000
======================================================================

======================================================================
>>> MQTT PUBLISH [2025-12-14T18:05:00.123456]
======================================================================
Topic: productId/uid/download/pointdata
Payload: {"common": {...}, "data": {...}}

----------------------------------------------------------------------
<<< MQTT MESSAGE [2025-12-14T18:05:01.234567]
----------------------------------------------------------------------
Topic: productId/uid/upload/pointdata
Payload: {"common": {...}, "data": {"mac": "10ba77692", "pointData": "..."}}
```

## Transport Modes

The program supports two transport modes for sending commands:

### MQTT Mode (Default)

- Commands sent via MQTT to the Topband cloud broker
- Real-time response via MQTT subscription
- Lower latency for command execution
- Requires MQTT listener to see responses

### HTTP Mode

- Commands sent via HTTPS REST API
- Synchronous request/response
- More reliable for one-off commands
- Automatically refreshes zone data after commands

## Status Display

The status command shows data source information:

- `(HTTP cache)` - Data from last HTTP API fetch
- `(MQTT: timestamp)` - Data updated from MQTT at the given time

When MQTT listener is running, status will reflect real-time updates from the heating system.

## PointIndex Reference

The MQTT updates show raw PointIndex values. Key indices:

| Index | Name | Description |
|-------|------|-------------|
| 5 | Current Temp | Current temperature × 10 (e.g., 195 = 19.5°C) |
| 6 | Target Temp | Target setpoint × 10 |
| 7 | Mode | 0=AUTO, 1=ALL_DAY, 2=ON, 3=OFF |
| 8 | Boost Hours | 0=inactive, 1-3=boost duration |
| 10 | Boiler State | 1=OFF, 2=ON |
| 14 | Boost Temp | Boost target temperature × 10 |

## Troubleshooting

### Connection Timeout

If you see "Read timed out" errors, the EPH API may be slow or unreachable. Try:
- Wait and retry
- Check if the EPH Ember mobile app works
- Check your internet connection

### MQTT Not Updating

If MQTT updates aren't reflected in status:
- Ensure MQTT listener is started: `mqtt start`
- Check MQTT status: `mqtt status`
- Use `-d` flag to see debug output

### Zone Not Found

If a zone is not found:
- Use `zones` to list available zone names
- Zone names are case-insensitive for matching
- You can use partial names (e.g., "living" matches "Living Room")

## Development

This tool is part of the pyephember2 development suite. It's designed to:

1. Test pyephember2 library functionality
2. Debug MQTT/HTTP communication
3. Reverse-engineer the EPH Controls protocol
4. Develop new features before integrating into Home Assistant

## License

MIT License - See LICENSE.txt
