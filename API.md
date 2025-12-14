# EPH Controls Ember / Topband API Specification

**Version:** 2.0 (Updated December 2025)

> **Note:** I have no connection with EPH Controls and this API may be subject to change. Use of this API is at your own risk. This is a reverse-engineered specification based on observation.

## API Versions

The Ember API was updated in January 2021. The document describing the old API from 2020 is available in [API_2020.md](API_2020.md).

## Overview

The Ember API is a dual HTTPS and MQTT system:

| Transport | Purpose |
|-----------|---------|
| **HTTP (REST/JSON)** | Authentication, admin, reading zone/home information |
| **MQTT (JSON + Binary)** | Real-time control and state updates |

**Key Insight:** HTTP is authoritative for commands; MQTT is reactive for state propagation. pyephember2 works without MQTT because MQTT is not required for control—only for passive updates.

## Endpoints

### HTTP

Base URL: `https://eu-https.topband-cloud.com/ember-back`

Referred to as `$HTTP_ENDPOINT` in this document.

### MQTT

Broker: `eu-base-mqtt.topband-cloud.com:18883` (TLS encrypted)

Referred to as `$MQTT_ENDPOINT` in this document.

---

# HTTP API

## Authentication

### Login

Initial login uses email and password. Subsequent requests use the access token.

#### Request

```
POST $HTTP_ENDPOINT/appLogin/login
Content-Type: application/json
Accept: application/json
```

```json
{
    "password": "password",
    "model": "iPhone XS",
    "os": "13.5",
    "type": 2,
    "appVersion": "2.0.4",
    "userName": "user@email.com"
}
```

#### Response

```json
{
    "data": {
        "refresh_token": "long_refresh_token",
        "token": "long_token"
    },
    "message": null,
    "status": 0,
    "timestamp": 1615150233365
}
```

- `token` - Used in `Authorization` header for all subsequent requests
- `refresh_token` - Used to refresh the token before expiry

### Refresh Token

```
GET $HTTP_ENDPOINT/appLogin/refreshAccessToken
Authorization: <refresh_token>
Accept: application/json
```

Token validity appears to be at least 1 hour.

## Home Information

### List Homes

```
GET $HTTP_ENDPOINT/homes/list
Authorization: <token>
```

#### Response

```json
{
    "data": [{
        "deviceType": 3,
        "gatewayid": "gwid1111",
        "invitecode": "DDDD",
        "name": "Home",
        "productId": "1234abcd",
        "uid": "011011",
        "zoneCount": 3
    }],
    "message": "succ.",
    "status": 0
}
```

### Home Details

```
POST $HTTP_ENDPOINT/homes/detail
Authorization: <token>

{"gateWayId": "gwid1111"}
```

Returns home configuration including `pointDataList` for home-level settings.

## Zone Information

### Get All Zones (Primary Method)

```
POST $HTTP_ENDPOINT/homesVT/zoneProgram
Authorization: <token>

{"gateWayId": "gwid1111"}
```

This is the primary endpoint for retrieving zone data. Response includes:

- Zone metadata (name, mac, zoneid, deviceType, systemType)
- Schedule data (deviceDays with p1/p2/p3 periods)
- Point data (pointDataList with current state)

#### Response Structure

```json
{
    "data": [{
        "deviceDays": [...],
        "deviceType": 2,
        "isonline": true,
        "mac": "10ba77692",
        "name": "Downstairs",
        "pointDataList": [
            {"pointIndex": 5, "value": "204"},
            {"pointIndex": 6, "value": "200"},
            {"pointIndex": 7, "value": "0"},
            ...
        ],
        "productId": "productid135",
        "systemType": "EMBER-PS",
        "uid": "uid011",
        "zoneid": "zoneid9b"
    }],
    "timestamp": 1615150236609
}
```

### Device Types

| deviceType | Description |
|------------|-------------|
| 2 | Thermostat |
| 4 | Hot Water Controller |
| 514 | Hot Water Controller (alternate) |
| 773 | Thermostatic Radiator Valve (TRV) |

### System Types

| systemType | Description |
|------------|-------------|
| EMBER-PS | Standard Ember system |

---

# MQTT API

## Connection

### Connect

```
Client ID: <userId>_<timestamp>
Username: app/<token>
Password: <token>
```

Where:
- `userId` - From `selectUser` HTTP response
- `token` - From login response
- `timestamp` - Unix timestamp in milliseconds

### Topics

| Topic Pattern | Direction | Purpose |
|---------------|-----------|---------|
| `<productId>/<uid>/upload/pointdata` | Device → Cloud | State updates from device |
| `<productId>/<uid>/download/pointdata` | Cloud → Device | Commands to device |

## Message Format

### Envelope (JSON)

```json
{
    "common": {
        "serial": 7870,
        "productId": "productid135",
        "uid": "uid011",
        "timestamp": "1765731704839",
        "userId": "1111"
    },
    "data": {
        "mac": "10ba77692",
        "pointData": "AAcBAw=="
    }
}
```

- `mac` - Identifies the target zone
- `pointData` - Base64-encoded binary attribute data

---

# Point Data Specification

## Binary Encoding

The `pointData` field contains Base64-encoded binary records:

```
[HEADER][INDEX][TYPE][VALUE...]
```

| Field | Size | Description |
|-------|------|-------------|
| Header | 1 byte | Always `0x00` (may be part of extended index) |
| Index | 1 byte | Point index (0-255) |
| Type | 1 byte | Data type identifier |
| Value | 1-4 bytes | Big-endian value |

Multiple records can be concatenated in a single payload.

## Data Types

| Type ID | Length | Description | Example |
|---------|--------|-------------|---------|
| 1 | 1 byte | Integer/enum/boolean | Mode, boost flag |
| 2 | 2 bytes | Temperature × 10 (read-only) | Current temp: 204 = 20.4°C |
| 4 | 2 bytes | Temperature × 10 (read-write) | Target temp: 200 = 20.0°C |
| 5 | 4 bytes | Unix timestamp (seconds) | Boost start time |

**Temperature Scale:** All temperatures are stored as `degreesC × 10`
- 19.5°C → 195
- 50.0°C → 500 (hot water)

## Zone Point Index Registry

### Confirmed Indices

| Index | Name | Type | Values | Status |
|-------|------|------|--------|--------|
| **5** | Current Temperature | 2 | temp × 10 | ✅ CONFIRMED |
| **6** | Target Temperature | 4 | temp × 10 | ✅ CONFIRMED |
| **7** | Zone Mode | 1 | 0=AUTO, 1=ALL_DAY, 2=ON, 3=OFF | ✅ CONFIRMED |
| **8** | Boost Hours | 1 | 0=inactive, 1-3=duration | ✅ CONFIRMED |
| **9** | Boost Start Time | 5 | Unix epoch (seconds) | ✅ CONFIRMED |
| **10** | Boiler/Heating State | 1 | 1=OFF, 2=ON | ✅ CONFIRMED |
| **14** | Boost Target Temperature | 4 | temp × 10 | ✅ CONFIRMED |

### Observed Indices (Needs Validation)

| Index | Name | Type | Notes |
|-------|------|------|-------|
| 3 | Zone mode (alt?) | 1 | Values 11, 12 observed |
| 4 | Advance Active | 1 | 0/1 toggle |
| 11 | Unknown flag | 1 | Often 0 |
| 13 | Enabled/Present flag | 1 | Always 1 |
| 15 | Schedule bitmap/counter | 5 | Changes with schedule |
| 16 | Capability bitmap | 5 | Often constant |
| 17 | Counter/telemetry | 5 | Often 0 |
| 18 | Counter/telemetry | 5 | Often 0 |

### Device-Specific Index Mapping

Some indices vary by `deviceType`:

| deviceType | MODE index | TARGET_TEMP index | Notes |
|------------|------------|-------------------|-------|
| 2 (Thermostat) | 7 | 6 | Standard |
| 4 (Hot Water) | 7 | 6 | Standard |
| 514 | 11 | 6 | Alternate mode index |
| 773 (TRV) | 11 | 12 | Different indices |

---

# Command Patterns

## Set Zone Mode (Turn Off)

**MQTT Downlink:**
```
Index 7, Type 1, Value 3 (OFF)
```

**Observed Response:**
```
i=7 value=3 (mode off)
i=10 value=1 (heating output off)
```

## Set Target Temperature

**MQTT Downlink:**
```
Index 6, Type 4, Value <temp×10>
```

Example: 20.5°C → Value 205

## Activate Boost

**MQTT Downlink (multiple points):**
```
i=8  t=1  v=<hours>           (1, 2, or 3)
i=9  t=5  v=<epoch_seconds>   (boost start time)
i=14 t=4  v=<temp×10>         (boost target temp)
```

## Cancel Boost

**MQTT Downlink:**
```
i=8 t=1 v=0
i=9 t=5 v=0
```

---

# Schedule Encoding

## Time Format

Schedule times are encoded in **10-minute units since midnight**:

```
encoded_time = (hours × 60 + minutes) ÷ 10
```

| Time | Encoded |
|------|---------|
| 07:00 | 42 |
| 08:30 | 51 |
| 17:00 | 102 |
| 23:50 | 143 |

**UI Constraint:** Only 10-minute increments are selectable.

## Period Structure

Each day has 3 periods (p1, p2, p3):

```json
{
    "dayType": 1,
    "p1": {"startTime": 42, "endTime": 51},
    "p2": {"startTime": 102, "endTime": 130},
    "p3": {"startTime": 170, "endTime": 180}
}
```

**Day Types:** 0=Sunday, 1=Monday, ... 6=Saturday

**Disabled Period:** When `startTime == endTime`, the period is disabled/empty.

---

# Implementation Notes

## pyephember2 Behavior

- Uses HTTP for zone data retrieval
- Uses MQTT for sending control commands
- Does not require MQTT subscription for basic control
- MQTT subscription enables real-time state updates

## Error Handling

- HTTP timeout: 10 seconds default
- API may be slow during peak times
- Retry with exponential backoff recommended

## Token Management

- Access token expires after ~30 minutes
- Refresh before expiry using `refresh_token`
- Re-login if refresh fails

---

# Changelog

## Version 2.0 (December 2025)

- Added confirmed PointIndex semantics from reverse-engineering
- Added MQTT command patterns for boost, mode, temperature
- Added schedule encoding specification
- Added device-type specific index mapping
- Clarified temperature scaling (×10)
- Added zone mode values (0=AUTO, 1=ALL_DAY, 2=ON, 3=OFF)
- Added boiler state values (1=OFF, 2=ON)

## Version 1.0 (March 2021)

- Initial documentation of 2021 API
- HTTP and MQTT endpoint documentation
- Basic point data structure
