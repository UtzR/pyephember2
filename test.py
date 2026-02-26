#!/usr/bin/env python3
"""
Debug and development test script for pyephember2.

This script logs in to the EPH Controls Ember heating system,
fetches information, and displays it in human-readable form
along with raw debug information for protocol analysis.
"""
import argparse
import getpass
import json
import logging
import sys
from datetime import datetime
from functools import wraps

# Enable debug logging for HTTP requests
import requests

# Import from local pyephember2
from pyephember2.pyephember2 import (
    EphEmber,
    ZoneMode,
    zone_name,
    zone_mode,
    zone_current_temperature,
    zone_target_temperature,
    zone_is_boost_active,
    zone_boost_hours,
    zone_is_hotwater,
    boiler_state,
    decode_point_data,
)


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def colored(text, color):
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.ENDC}"


HTTP_LOG_FILE = "test_log_http"
MQTT_LOG_FILE = "test_log_mqtt"


def init_http_log():
    """Initialize the HTTP log file (empty it)."""
    with open(HTTP_LOG_FILE, 'w') as f:
        f.write(f"# HTTP Communication Log\n")
        f.write(f"# Started: {datetime.now().isoformat()}\n")
        f.write(f"{'='*70}\n\n")


def init_mqtt_log():
    """Initialize the MQTT log file (empty it)."""
    with open(MQTT_LOG_FILE, 'w') as f:
        f.write(f"# MQTT Communication Log\n")
        f.write(f"# Started: {datetime.now().isoformat()}\n")
        f.write(f"{'='*70}\n\n")


def log_http(direction, content):
    """Log HTTP communication to file.
    
    Args:
        direction: 'SEND' or 'RECV'
        content: The content to log
    """
    with open(HTTP_LOG_FILE, 'a') as f:
        timestamp = datetime.now().isoformat()
        if direction == 'SEND':
            f.write(f"\n{'='*70}\n")
            f.write(f">>> SENDING REQUEST [{timestamp}]\n")
            f.write(f"{'='*70}\n")
        else:
            f.write(f"\n{'-'*70}\n")
            f.write(f"<<< RECEIVED RESPONSE [{timestamp}]\n")
            f.write(f"{'-'*70}\n")
        f.write(content)
        f.write("\n")


def log_mqtt(direction, content):
    """Log MQTT communication to file.
    
    Args:
        direction: 'SEND', 'RECV', or 'INFO'
        content: The content to log
    """
    with open(MQTT_LOG_FILE, 'a') as f:
        timestamp = datetime.now().isoformat()
        if direction == 'SEND':
            f.write(f"\n{'='*70}\n")
            f.write(f">>> MQTT PUBLISH [{timestamp}]\n")
            f.write(f"{'='*70}\n")
        elif direction == 'RECV':
            f.write(f"\n{'-'*70}\n")
            f.write(f"<<< MQTT MESSAGE [{timestamp}]\n")
            f.write(f"{'-'*70}\n")
        else:  # INFO
            f.write(f"\n[{timestamp}] {direction}: ")
        f.write(content)
        f.write("\n")


def setup_logging(debug_level):
    """Configure logging based on debug level."""
    if debug_level >= 2:
        # Full HTTP debug - show request/response bodies
        logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')
        # Enable urllib3 debug logging
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        # Enable MQTT debug logging
        logging.getLogger("pyephember2.mqtt").setLevel(logging.DEBUG)
        # Enable requests debug logging
        try:
            import http.client as http_client
            http_client.HTTPConnection.debuglevel = 1
        except Exception:
            pass
    elif debug_level >= 1:
        logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
        # Enable MQTT info logging
        logging.getLogger("pyephember2.mqtt").setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


def patch_http_for_debug(ember_instance, verbose_console=False):
    """Monkey-patch the _http method to log requests and responses."""
    original_http = ember_instance._http
    
    @wraps(original_http)
    def debug_http(endpoint, *, method=requests.post, headers=None,
                   send_token=False, data=None, timeout=10):
        # Build request log
        request_log = f"Method: {method.__name__.upper()}\n"
        request_log += f"Endpoint: {endpoint}\n"
        request_log += f"Send Token: {send_token}\n"
        request_log += f"Timeout: {timeout}\n"
        if data:
            request_log += "Data:\n"
            if isinstance(data, dict):
                request_log += json.dumps(data, indent=2)
            else:
                request_log += str(data)
        
        # Log to file
        log_http('SEND', request_log)
        
        # Console output if verbose
        if verbose_console:
            print(colored(f"\n{'='*60}", Colors.DIM))
            print(colored(f"HTTP REQUEST: {method.__name__.upper()} {endpoint}", Colors.CYAN))
            if data:
                print(colored("Request Data:", Colors.DIM))
                if isinstance(data, dict):
                    print(colored(json.dumps(data, indent=2), Colors.DIM))
                else:
                    print(colored(str(data), Colors.DIM))
        
        # Make the actual request
        response = original_http(endpoint, method=method, headers=headers,
                                  send_token=send_token, data=data, timeout=timeout)
        
        # Build response log
        response_log = f"Status Code: {response.status_code}\n"
        try:
            resp_json = response.json()
            response_log += "Body:\n"
            response_log += json.dumps(resp_json, indent=2)
        except Exception:
            response_log += f"Body (text): {response.text}"
        
        # Log to file
        log_http('RECV', response_log)
        
        # Console output if verbose
        if verbose_console:
            print(colored(f"HTTP RESPONSE: {response.status_code}", Colors.GREEN if response.status_code == 200 else Colors.RED))
            try:
                resp_json = response.json()
                print(colored("Response Data:", Colors.DIM))
                # Truncate very long responses for console
                resp_str = json.dumps(resp_json, indent=2)
                if len(resp_str) > 2000:
                    print(colored(resp_str[:2000] + "\n... (truncated)", Colors.DIM))
                else:
                    print(colored(resp_str, Colors.DIM))
            except Exception:
                print(colored(f"Response Text: {response.text[:500]}", Colors.DIM))
            print(colored(f"{'='*60}\n", Colors.DIM))
        
        return response
    
    ember_instance._http = debug_http


def print_header(text):
    """Print a section header."""
    print(f"\n{colored('='*60, Colors.BLUE)}")
    print(colored(f"  {text}", Colors.BOLD + Colors.BLUE))
    print(colored('='*60, Colors.BLUE))


def print_subheader(text):
    """Print a subsection header."""
    print(f"\n{colored('-'*40, Colors.CYAN)}")
    print(colored(f"  {text}", Colors.CYAN))
    print(colored('-'*40, Colors.CYAN))


def decode_time(encoded_time):
    """
    Decode schedule time format to HH:MM.
    The API uses a format where the integer represents HHMM where the last digit
    is 10-minute units. For example: 90 = 09:00, 100 = 10:00, 173 = 17:30.
    This matches the scheduletime_to_time function in pyephember2.py.
    """
    if encoded_time is None:
        return "N/A"
    # Convert to string to extract digits
    time_str = str(encoded_time)
    if len(time_str) == 0:
        return "00:00"
    # Last digit is 10-minute units, rest is hours
    hours = int(time_str[:-1]) if len(time_str) > 1 else 0
    minutes = 10 * int(time_str[-1])
    return f"{hours:02d}:{minutes:02d}"


def format_temperature(temp):
    """Format temperature value."""
    if temp is None:
        return "N/A"
    return f"{temp:.1f}°C"


def format_mode(mode):
    """Format zone mode."""
    if mode is None:
        return colored("UNKNOWN (None)", Colors.RED)
    return f"{mode.name} ({mode.value})"


def format_boiler_state(state):
    """Format boiler state."""
    states = {0: "UNKNOWN", 1: "OFF", 2: "ON"}
    name = states.get(state, f"UNKNOWN({state})")
    color = Colors.GREEN if state == 2 else Colors.DIM
    return colored(name, color)


def print_pointdata_table(zone):
    """Print all PointData values in a table format."""
    print_subheader("Raw PointData")
    
    device_type = zone.get("deviceType")
    
    # Generic point indices (all device types)
    generic_meanings = {
        4: "Advance On / Off (0/1 toggle)",
        5: "Current Temp (temp × 10)",
        14: "Setpoint (Boost) (temp × 10)",
    }
    
    # Device-type-specific point indices
    match device_type:
        case 2 | 4:
            point_meanings = {
                **generic_meanings,
                6: "Setpoint (Any Mode) (temp × 10)",
                7: "Mode (0=auto, 1=all day, 2=on, 3=off)",
                8: "Boost Hours (0 to 3)",
                9: "Boost Start Time (Unix epoch)",
                10: "Boiler State (1=off, 2=on)",
            }
            important_indices = (4, 5, 6, 7, 8, 9, 10, 14)
        case 258:
            point_meanings = {
                **generic_meanings,
                6: "Setpoint (Read Only) (temp × 10)",
                7: "Hi Temp Limit (temp × 10)",
                8: "Lo Temp Limit (temp × 10)",
                11: "Mode (0=AUTO, 1=ON/MANUAL, 4=OFF)",
                12: "Setpoint (Man Mode) (temp × 10)",
                13: "Boost State (0=Inactive, 1=Active)",
                15: "Boost End Time (Unix timestamp or 0)",
                16: "Schedule Active Flag (1/0)",
                17: "Setpoint (Auto Mode) (temp × 10)",
                18: "Boiler State (1=off, 2=on)",
            }
            important_indices = (4, 5, 6, 7, 8, 11, 12, 13, 15, 16, 17, 18)
        case 514 | 516:
            # EMBER-PS2 thermostat (514) and hot water (516) share the same point layout
            point_meanings = {
                **generic_meanings,
                6: "Setpoint (Read Only) (temp × 10)",
                7: "Hi Temp Limit (temp × 10)",
                8: "Lo Temp Limit (temp × 10)",
                11: "Mode (0=AUTO, 4=OFF, 9=ALL DAY, 10=ON/MANUAL)",
                12: "Manual Mode Setpoint (temp × 10)",
                13: "Boost State (0=Inactive, 1=Active)",
                15: "Boost End Time (Unix timestamp or 0)",
                16: "Schedule Active Flag (1/0)",
                18: "Boiler State (1=off, 2=on)",
            }
            important_indices = (4, 5, 6, 7, 8, 11, 12, 13, 15, 16, 18)
        case 773:
            point_meanings = {
                **generic_meanings,
                11: "Mode (0=AUTO, 1=ON/MANUAL, 4=OFF)",
                12: "Manual Mode Setpoint (temp × 10)",
                13: "Boost State (0=Inactive, 1=Active, might be hours)",
                15: "Boost End Time (Unix timestamp or 0)",
            }
            important_indices = (4, 5, 11, 12, 13, 14, 15)
        case _:
            # Unknown device type - use generic only
            point_meanings = generic_meanings.copy()
            important_indices = (4, 5, 14)
    
    print(f"{'Index':<8} {'Value':<15} {'Hex':<12} {'Meaning':<35}")
    print("-" * 70)
    
    for datum in sorted(zone.get('pointDataList', []), key=lambda x: x['pointIndex']):
        idx = datum['pointIndex']
        val = datum['value']
        hex_val = hex(int(val)) if isinstance(val, (int, float)) else "N/A"
        meaning = point_meanings.get(idx, "")
        
        # Highlight important indices based on device type
        if idx in important_indices:
            print(colored(f"{idx:<8} {val:<15} {hex_val:<12} {meaning:<35}", Colors.GREEN))
        else:
            print(f"{idx:<8} {val:<15} {hex_val:<12} {meaning:<35}")


def print_schedule(zone):
    """Print schedule information for a zone."""
    print_subheader("Schedule (deviceDays)")
    
    days_of_week = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    device_days = zone.get('deviceDays', [])
    if not device_days:
        print(colored("  No schedule data available", Colors.DIM))
        return
    
    device_type = zone.get("deviceType")
    
    # Determine schedule format based on device type
    # deviceType 258 = EMBER-TS2: p1-p6 with "time" and "temperature"
    # deviceType 2, 4, 514, 516 = EMBER-PS/EMBER-PS2: p1-p3 with "startTime" and "endTime"
    # Other device types: unknown format
    
    if device_type == 258:
        # EMBER-TS2 format: 6 periods (p1-p6) with time and temperature
        schedule_format = "EMBER-TS2"
        num_periods = 6
    elif device_type in (2, 4, 514, 516):
        # EMBER-PS/EMBER-PS2 format: 3 periods (p1-p3) with startTime/endTime
        schedule_format = "EMBER-PS" if device_type in (2, 4) else "EMBER-PS2"
        num_periods = 3
    else:
        # Unknown format - try to detect
        schedule_format = "Unknown"
        # Check first day to see what format it uses
        if device_days:
            first_day = device_days[0]
            # Check if it has p1 with "time" field (EMBER-TS format)
            p1 = first_day.get('p1', {})
            if isinstance(p1, dict) and 'time' in p1 and 'startTime' not in p1:
                schedule_format = "Detected: EMBER-TS-like (time-based)"
                num_periods = 6  # Try 6 periods
            # Check if it has p1 with "startTime" field (EMBER-PS format)
            elif isinstance(p1, dict) and 'startTime' in p1:
                schedule_format = "Detected: EMBER-PS-like (range-based)"
                num_periods = 3  # Try 3 periods
            else:
                schedule_format = "Unknown format"
                num_periods = 3  # Default fallback
    
    print(f"  Schedule Format: {colored(schedule_format, Colors.YELLOW)}")
    
    for day in sorted(device_days, key=lambda x: x.get('dayType', 0)):
        day_type = day.get('dayType', 0)
        day_name = days_of_week[day_type] if 0 <= day_type < 7 else f"Day {day_type}"
        
        print(f"\n  {colored(day_name, Colors.BOLD)}:")
        
        if schedule_format.startswith("EMBER-TS"):
            # EMBER-TS2 format: p1-p6 with time and temperature
            for p_num in range(1, num_periods + 1):
                p_key = f'p{p_num}'
                period = day.get(p_key)
                if period and isinstance(period, dict):
                    time_value = period.get('time')
                    temp = period.get('temperature')
                    
                    if time_value is not None:
                        time_str = decode_time(time_value)
                        temp_str = f" @ {temp/10:.1f}°C" if temp is not None else ""
                        print(f"    P{p_num}: {time_str}{temp_str}")
                    else:
                        print(colored(f"    P{p_num}: Not defined (no time)", Colors.DIM))
                else:
                    print(colored(f"    P{p_num}: Not defined", Colors.DIM))
        
        elif schedule_format.startswith("EMBER-PS"):
            # EMBER-PS/EMBER-PS2 format: p1-p3 with startTime/endTime
            for p_num in range(1, num_periods + 1):
                p_key = f'p{p_num}'
                period = day.get(p_key)
                if period and isinstance(period, dict):
                    start = period.get('startTime')
                    end = period.get('endTime')
                    temp = period.get('temperature')
                    
                    start_str = decode_time(start)
                    end_str = decode_time(end)
                    
                    # Check for disabled period (start == end or None)
                    if start is None or end is None:
                        print(colored(f"    P{p_num}: Not defined (missing time)", Colors.DIM))
                    elif start == end:
                        print(colored(f"    P{p_num}: DISABLED (start == end)", Colors.DIM))
                    else:
                        temp_str = f" @ {temp/10:.1f}°C" if temp is not None else ""
                        print(f"    P{p_num}: {start_str} - {end_str}{temp_str}")
                else:
                    print(colored(f"    P{p_num}: Not defined", Colors.DIM))
        
        else:
            # Unknown format - display raw data
            print(colored(f"    Unknown schedule format for device type {device_type}", Colors.RED))
            for p_num in range(1, min(num_periods + 1, 7)):
                p_key = f'p{p_num}'
                period = day.get(p_key)
                if period:
                    print(f"    P{p_num}: {json.dumps(period)}")
                else:
                    print(colored(f"    P{p_num}: Not defined", Colors.DIM))


def format_device_type(device_type):
    """Format device type with known descriptions."""
    device_models = {
        2: "Thermostat (RX7-RF)",
        4: "Hot Water (RX7-RF)",
        258: "Thermostat (RF1A-OT)",
        514: "Thermostat (RX7-RF-V2)",
        516: "Hot Water (RX7-RF-V2)",
        773: "TRV (RF16?)",
    }
    description = device_models.get(device_type, "Unknown")
    return f"{device_type} ({description})"


def print_zone_summary(zone, ember):
    """Print a human-readable summary of a zone."""
    name = zone_name(zone)
    zone_id = zone.get('zoneid', 'N/A')
    device_type = zone.get('deviceType', 'N/A')
    system_type = zone.get('systemType', 'N/A')
    product_id = zone.get('productId', 'N/A')
    uid = zone.get('uid', 'N/A')
    mac = zone.get('mac', 'N/A')
    is_online = zone.get('isonline', 'N/A')
    
    print_subheader(f"Zone: {name}")
    
    print(f"  Zone ID:      {zone_id}")
    print(f"  System Type:  {colored(system_type, Colors.CYAN)}")
    print(f"  Device Type:  {format_device_type(device_type)}")
    print(f"  Online:       {colored('Yes', Colors.GREEN) if is_online else colored('No', Colors.RED)}")
    print(f"  Product ID:   {product_id}")
    print(f"  UID:          {uid}")
    print(f"  MAC:          {mac}")
    print(f"  Is Hot Water: {zone_is_hotwater(zone)}")
    print()
    
    # Temperatures
    current = zone_current_temperature(zone)
    target = zone_target_temperature(zone)
    print(f"  Current Temp: {format_temperature(current)}")
    print(f"  Target Temp:  {format_temperature(target)}")
    print()
    
    # Mode and state
    mode = zone_mode(zone)
    print(f"  Mode:         {format_mode(mode)}")
    print(f"  Boiler State: {format_boiler_state(boiler_state(zone))}")
    print()
    
    # Boost
    boost_active = zone_is_boost_active(zone)
    boost_hours = zone_boost_hours(zone)
    print(f"  Boost Active: {colored('YES', Colors.YELLOW) if boost_active else 'No'}")
    print(f"  Boost Hours:  {boost_hours}")


def print_raw_zone(zone):
    """Print raw zone data as JSON."""
    print_subheader("Raw Zone JSON")
    # Remove some verbose nested data for readability
    zone_copy = dict(zone)
    if 'days' in zone_copy:
        zone_copy['days'] = f"<{len(zone_copy['days'])} days - use --full-raw to see>"
    if 'deviceDays' in zone_copy:
        zone_copy['deviceDays'] = f"<{len(zone_copy['deviceDays'])} days - use --full-raw to see>"
    print(json.dumps(zone_copy, indent=2, default=str))


def print_zone_status(zone):
    """Print compact status for a zone (subset of fields)."""
    name = zone_name(zone)
    
    # Check if we have MQTT update timestamp
    mqtt_update = zone.get('_last_mqtt_update')
    if mqtt_update:
        update_info = colored(f"(MQTT: {mqtt_update})", Colors.DIM)
    else:
        update_info = colored("(HTTP cache)", Colors.DIM)
    
    print(f"\n  {colored(name, Colors.BOLD + Colors.CYAN)} {update_info}")
    print(f"  Is Hot Water:  {zone_is_hotwater(zone)}")
    
    current = zone_current_temperature(zone)
    target = zone_target_temperature(zone)
    print(f"  Current Temp:  {format_temperature(current)}")
    print(f"  Target Temp:   {format_temperature(target)}")
    
    mode = zone_mode(zone)
    print(f"  Mode:          {format_mode(mode)}")
    
    boost_active = zone_is_boost_active(zone)
    boost_hrs = zone_boost_hours(zone)
    print(f"  Boost Active:  {colored('YES', Colors.YELLOW) if boost_active else 'No'}")
    print(f"  Boost Hours:   {boost_hrs}")


def find_zone(homes, zone_query):
    """Find a zone by name or ID. Returns (zone, zone_id) or (None, None)."""
    query_lower = zone_query.lower()
    for home in homes:
        for zone in home.get('zones', []):
            name = zone_name(zone)
            zone_id = zone.get('zoneid', '')
            if query_lower in name.lower() or zone_query == zone_id:
                return zone, zone_id
    return None, None


def list_zone_names(homes):
    """Return a list of all zone names."""
    names = []
    for home in homes:
        for zone in home.get('zones', []):
            names.append(zone_name(zone))
    return names


def print_cli_help(transport_mode):
    """Print help for interactive CLI commands."""
    transport_str = colored(f"[{transport_mode.upper()}]", Colors.YELLOW)
    print(f"""
{colored('Available Commands:', Colors.BOLD + Colors.CYAN)}

  {colored('help', Colors.GREEN)}
      Display this help message

  {colored('status <zone>', Colors.GREEN)}
      Show current status of a zone
      Example: status Living Room

  {colored('schedule <zone>', Colors.GREEN)}
      Show the schedule for a zone
      Example: schedule Heating

  {colored('pointindex <zone>', Colors.GREEN)}
      Show the point index table for a zone
      Example: pointindex Heating

  {colored('boost <zone> [duration]', Colors.GREEN)} {transport_str}
      Boost a zone for the specified duration (default: 1 hour)
      Duration can be 0 (cancel), 1, 2, or 3 hours
      Example: boost Heating 2

  {colored('on <zone>', Colors.GREEN)} {transport_str}
      Turn a zone on (set mode to ON)
      Example: on Living Room

  {colored('off <zone>', Colors.GREEN)} {transport_str}
      Turn a zone off (set mode to OFF)
      Example: off Living Room

  {colored('temp <zone> <temperature>', Colors.GREEN)} {transport_str}
      Set target temperature for a zone
      Example: temp Living Room 21.5

  {colored('mode [http|mqtt]', Colors.GREEN)}
      Switch transport mode for commands (current: {transport_str})
      Example: mode mqtt

  {colored('mqtt status', Colors.GREEN)}
      Show MQTT connection status

  {colored('mqtt start', Colors.GREEN)}
      Start MQTT listener for receiving updates

  {colored('mqtt stop', Colors.GREEN)}
      Stop MQTT listener

  {colored('refresh', Colors.GREEN)}
      Refresh zone data from the HTTP API

  {colored('zones', Colors.GREEN)}
      List all available zone names

  {colored('exit', Colors.GREEN)} / {colored('quit', Colors.GREEN)}
      Exit the program

{colored('Note:', Colors.DIM)} Commands marked with {transport_str} use the current transport mode.
      Commands always use MQTT for sending (HTTP is used for data refresh).
""")


def on_mqtt_pointdata(mac, parsed_data):
    """Callback for MQTT pointData updates."""
    print(colored(f"\n  [MQTT] Received update for MAC {mac}:", Colors.YELLOW))
    for idx, data in sorted(parsed_data.items()):
        print(f"    PointIndex {idx}: {data['value']}")
    print(colored("eph> ", Colors.GREEN), end='', flush=True)


def get_current_homes(ember, fallback_homes):
    """Get the current homes from ember, with fallback to passed homes.
    
    This ensures we always see the latest data including MQTT updates.
    """
    return ember._homes if ember._homes else fallback_homes


def run_interactive_cli(ember, homes):
    """Run the interactive command-line interface."""
    print_header("Interactive Mode")
    print("  Type 'help' for available commands, 'exit' to quit.\n")
    
    # Transport mode: 'mqtt' or 'http' (mqtt is default since that's what pyephember2 uses)
    transport_mode = 'mqtt'
    
    # Set up MQTT logging callback
    ember.set_mqtt_log_callback(log_mqtt)
    
    while True:
        try:
            # Show prompt with transport mode indicator
            mode_indicator = colored(f"[{transport_mode}]", Colors.YELLOW if transport_mode == 'mqtt' else Colors.CYAN)
            user_input = input(colored("eph", Colors.GREEN) + mode_indicator + colored("> ", Colors.GREEN)).strip()
            
            if not user_input:
                continue
            
            # Parse command and arguments
            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()
            args_str = parts[1] if len(parts) > 1 else ""
            
            # Handle commands
            if command in ('exit', 'quit'):
                # Stop MQTT if running
                if ember.is_mqtt_connected():
                    ember.stop_mqtt_listener()
                print(colored("  Goodbye!", Colors.CYAN))
                break
            
            elif command == 'help':
                print_cli_help(transport_mode)
            
            elif command == 'zones':
                current_homes = get_current_homes(ember, homes)
                names = list_zone_names(current_homes)
                print(f"\n  {colored('Available zones:', Colors.CYAN)}")
                for name in names:
                    print(f"    - {name}")
                print()
            
            elif command == 'refresh':
                print("  Refreshing zone data...")
                try:
                    ember.NextHomeUpdateDaytime = None
                    homes = ember.get_zones()
                    total_zones = sum(len(home.get('zones', [])) for home in homes)
                    print(colored(f"  ✓ Refreshed {total_zones} zone(s)", Colors.GREEN))
                except Exception as e:
                    print(colored(f"  ✗ Failed to refresh: {e}", Colors.RED))
            
            elif command == 'status':
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: status <zone>")
                    continue
                
                # Always get current homes from ember (includes MQTT updates)
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, args_str)
                if zone:
                    print_zone_status(zone)
                else:
                    print(colored(f"  Error: Zone '{args_str}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'schedule':
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: schedule <zone>")
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, args_str)
                if zone:
                    print(f"\n  {colored(zone_name(zone), Colors.BOLD + Colors.CYAN)}")
                    print_schedule(zone)
                else:
                    print(colored(f"  Error: Zone '{args_str}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'pointindex':
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: pointindex <zone>")
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, args_str)
                if zone:
                    print(f"\n  {colored(zone_name(zone), Colors.BOLD + Colors.CYAN)}")
                    print_pointdata_table(zone)
                else:
                    print(colored(f"  Error: Zone '{args_str}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'boost':
                # Parse: boost <zone> [duration]
                boost_parts = args_str.rsplit(maxsplit=1)
                
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: boost <zone> [duration]")
                    continue
                
                # Check if last part is a number (duration)
                duration = 1  # default
                zone_query = args_str
                
                if len(boost_parts) == 2:
                    try:
                        duration = int(boost_parts[1])
                        zone_query = boost_parts[0]
                    except ValueError:
                        # Last part is not a number, treat whole thing as zone name
                        pass
                
                if duration not in (0, 1, 2, 3):
                    print(colored(f"  Error: Duration must be 0, 1, 2, or 3 hours", Colors.RED))
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, zone_query)
                if zone:
                    try:
                        if duration == 0:
                            print(f"  Cancelling boost for {zone_name(zone)} via {transport_mode.upper()}...")
                            if transport_mode == 'mqtt':
                                ember.deactivate_zone_boost_mqtt(zone_id)
                            else:
                                ember.deactivate_zone_boost(zone_id)
                            print(colored("  ✓ Boost cancelled", Colors.GREEN))
                        else:
                            print(f"  Boosting {zone_name(zone)} for {duration} hour(s) via {transport_mode.upper()}...")
                            if transport_mode == 'mqtt':
                                ember.activate_zone_boost_mqtt(zone_id, num_hours=duration)
                            else:
                                ember.activate_zone_boost(zone_id, num_hours=duration)
                            print(colored(f"  ✓ Boost activated for {duration}h", Colors.GREEN))
                    except Exception as e:
                        print(colored(f"  ✗ Failed: {e}", Colors.RED))
                else:
                    print(colored(f"  Error: Zone '{zone_query}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'on':
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: on <zone>")
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, args_str)
                if zone:
                    try:
                        print(f"  Turning on {zone_name(zone)} via {transport_mode.upper()}...")
                        if transport_mode == 'mqtt':
                            ember.turn_zone_on_mqtt(zone_id)
                        else:
                            ember.set_zone_mode(zone_id, ZoneMode.ON)
                        print(colored("  ✓ Zone turned ON", Colors.GREEN))
                    except Exception as e:
                        print(colored(f"  ✗ Failed: {e}", Colors.RED))
                else:
                    print(colored(f"  Error: Zone '{args_str}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'off':
                if not args_str:
                    print(colored("  Error: Please specify a zone name", Colors.RED))
                    print("  Usage: off <zone>")
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, args_str)
                if zone:
                    try:
                        print(f"  Turning off {zone_name(zone)} via {transport_mode.upper()}...")
                        if transport_mode == 'mqtt':
                            ember.turn_zone_off_mqtt(zone_id)
                        else:
                            ember.set_zone_mode(zone_id, ZoneMode.OFF)
                        print(colored("  ✓ Zone turned OFF", Colors.GREEN))
                    except Exception as e:
                        print(colored(f"  ✗ Failed: {e}", Colors.RED))
                else:
                    print(colored(f"  Error: Zone '{args_str}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'temp':
                # Parse: temp <zone> <temperature>
                temp_parts = args_str.rsplit(maxsplit=1)
                
                if len(temp_parts) < 2:
                    print(colored("  Error: Please specify zone and temperature", Colors.RED))
                    print("  Usage: temp <zone> <temperature>")
                    continue
                
                zone_query = temp_parts[0]
                try:
                    temperature = float(temp_parts[1])
                except ValueError:
                    print(colored(f"  Error: Invalid temperature '{temp_parts[1]}'", Colors.RED))
                    continue
                
                current_homes = get_current_homes(ember, homes)
                zone, zone_id = find_zone(current_homes, zone_query)
                if zone:
                    try:
                        print(f"  Setting {zone_name(zone)} to {temperature}°C via {transport_mode.upper()}...")
                        if transport_mode == 'mqtt':
                            ember.set_zone_target_temperature_mqtt(zone_id, temperature)
                        else:
                            ember.set_zone_target_temperature(zone_id, temperature)
                        print(colored(f"  ✓ Temperature set to {temperature}°C", Colors.GREEN))
                    except Exception as e:
                        print(colored(f"  ✗ Failed: {e}", Colors.RED))
                else:
                    print(colored(f"  Error: Zone '{zone_query}' not found", Colors.RED))
                    print(f"  Available zones: {', '.join(list_zone_names(current_homes))}")
            
            elif command == 'mode':
                if not args_str:
                    print(f"  Current transport mode: {colored(transport_mode.upper(), Colors.YELLOW)}")
                    print("  Usage: mode [http|mqtt]")
                elif args_str.lower() in ('http', 'mqtt'):
                    transport_mode = args_str.lower()
                    print(f"  Transport mode set to: {colored(transport_mode.upper(), Colors.YELLOW)}")
                else:
                    print(colored(f"  Error: Unknown mode '{args_str}'", Colors.RED))
                    print("  Valid modes: http, mqtt")
            
            elif command == 'mqtt':
                mqtt_cmd = args_str.lower().split()[0] if args_str else ""
                
                if mqtt_cmd == 'status':
                    if ember.is_mqtt_connected():
                        print(colored("  MQTT: Connected", Colors.GREEN))
                    else:
                        print(colored("  MQTT: Not connected", Colors.DIM))
                
                elif mqtt_cmd == 'start':
                    if ember.is_mqtt_connected():
                        print(colored("  MQTT listener already running", Colors.YELLOW))
                    else:
                        print("  Starting MQTT listener...")
                        try:
                            # Get all zones for subscription
                            current_homes = get_current_homes(ember, homes)
                            all_zones = []
                            for home in current_homes:
                                all_zones.extend(home.get('zones', []))
                            
                            # Set up callback for received data
                            ember.set_mqtt_pointdata_callback(on_mqtt_pointdata)
                            
                            # Start listener
                            ember.start_mqtt_listener(all_zones)
                            print(colored(f"  ✓ MQTT listener started, subscribed to {len(all_zones)} zone(s)", Colors.GREEN))
                        except Exception as e:
                            print(colored(f"  ✗ Failed to start MQTT: {e}", Colors.RED))
                
                elif mqtt_cmd == 'stop':
                    if ember.is_mqtt_connected():
                        ember.stop_mqtt_listener()
                        print(colored("  ✓ MQTT listener stopped", Colors.GREEN))
                    else:
                        print(colored("  MQTT listener not running", Colors.DIM))
                
                else:
                    print("  MQTT commands:")
                    print("    mqtt status  - Show connection status")
                    print("    mqtt start   - Start MQTT listener")
                    print("    mqtt stop    - Stop MQTT listener")
            
            else:
                print(colored(f"  Unknown command: {command}", Colors.RED))
                print("  Type 'help' for available commands")
        
        except KeyboardInterrupt:
            print(colored("\n  Use 'exit' or 'quit' to exit.", Colors.YELLOW))
        
        except EOFError:
            print(colored("\n  Goodbye!", Colors.CYAN))
            break
    
    return homes  # Return potentially updated homes


def main():
    parser = argparse.ArgumentParser(
        prog='test.py',
        description='Debug and development tool for pyephember2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test.py --email user@example.com
  python test.py --email user@example.com --debug
  python test.py --email user@example.com --debug --debug  # Extra verbose
  python test.py --email user@example.com --zone "Living Room"
  python test.py --email user@example.com --set-temp 20.5 --zone "Living Room"
        """
    )
    
    # Authentication
    parser.add_argument("--email", type=str, required=True,
                        help="Email address for your EPH account")
    parser.add_argument('--password', type=str, default="",
                        help="Password (will prompt if not provided)")
    
    # Debug options
    parser.add_argument('--debug', '-d', action='count', default=0,
                        help="Enable debug output (-d for info, -dd for full HTTP debug)")
    parser.add_argument('--http-debug', action='store_true',
                        help="Show raw HTTP requests and responses")
    parser.add_argument('--full-raw', action='store_true',
                        help="Show full raw JSON without truncation")
    
    # Zone selection
    parser.add_argument('--zone', type=str,
                        help="Zone name or ID to focus on (shows all if not specified)")
    
    # Actions
    parser.add_argument('--set-temp', type=float,
                        help="Set target temperature for specified zone")
    parser.add_argument('--set-mode', type=str, choices=['AUTO', 'ON', 'OFF', 'ALL_DAY'],
                        help="Set mode for specified zone")
    parser.add_argument('--boost', type=int, choices=[0, 1, 2, 3],
                        help="Set boost hours (0 to cancel)")
    
    # Output options
    parser.add_argument('--json', action='store_true',
                        help="Output raw JSON only (for piping to other tools)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.debug)
    
    # Get password
    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
    
    # Initialize log files (empty them)
    init_http_log()
    init_mqtt_log()
    
    print_header("Connecting to EPH Controls Ember")
    print(f"  Email: {args.email}")
    print(f"  Debug Level: {args.debug}")
    print(f"  HTTP Log: {HTTP_LOG_FILE}")
    print(f"  MQTT Log: {MQTT_LOG_FILE}")
    
    try:
        # Create ember instance
        ember = EphEmber(args.email, password)
        print(colored("  ✓ Login successful", Colors.GREEN))
        
        # Always patch HTTP for file logging, verbose console output based on flags
        verbose_console = args.http_debug or args.debug >= 2
        patch_http_for_debug(ember, verbose_console=verbose_console)
        print(colored("  ✓ HTTP logging enabled", Colors.GREEN))
        if verbose_console:
            print(colored("  ✓ Verbose HTTP console output enabled", Colors.YELLOW))
        
    except RuntimeError as e:
        print(colored(f"  ✗ Login failed: {e}", Colors.RED))
        sys.exit(1)
    
    # Fetch zones
    print_header("Fetching Zone Data")
    
    try:
        homes = ember.get_zones()
        total_zones = sum(len(home.get('zones', [])) for home in homes)
        print(colored(f"  ✓ Found {len(homes)} home(s) with {total_zones} zone(s)", Colors.GREEN))
    except Exception as e:
        print(colored(f"  ✗ Failed to fetch zones: {e}", Colors.RED))
        sys.exit(1)
    
    # If JSON output requested, just dump and exit
    if args.json:
        print(json.dumps(homes, indent=2, default=str))
        sys.exit(0)
    
    # Process each home and zone
    for home_idx, home in enumerate(homes):
        home_name = home.get('name', f'Home {home_idx}')
        gateway_id = home.get('gatewayid', 'N/A')
        
        print_header(f"Home: {home_name}")
        print(f"  Gateway ID: {gateway_id}")
        
        zones = home.get('zones', [])
        
        for zone in zones:
            name = zone_name(zone)
            zone_id = zone.get('zoneid', '')
            
            # Filter by zone if specified
            if args.zone:
                if args.zone.lower() not in name.lower() and args.zone != zone_id:
                    continue
            
            # Print zone information
            print_zone_summary(zone, ember)
            print_pointdata_table(zone)
            print_schedule(zone)
            
            if args.debug >= 1 or args.full_raw:
                print_raw_zone(zone)
    
    # Enter interactive CLI mode
    run_interactive_cli(ember, homes)
    
    print_header("Session Ended")
    print(f"  Timestamp: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
