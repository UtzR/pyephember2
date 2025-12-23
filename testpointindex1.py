#!/usr/bin/env python3
"""
PointIndex Analysis Test Program for pyephember2.

This script systematically analyzes which user actions result in which
pointIndex changes by running a controlled test sequence.
Uses HTTP only (no MQTT).
"""
import argparse
import getpass
import sys
import time
from typing import Optional

from pyephember2.pyephember2 import (
    EphEmber,
    ZoneMode,
    zone_name,
    zone_is_hotwater,
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


def extract_pointdata_list(zone):
    """
    Extract pointDataList from zone dictionary.
    
    Args:
        zone: Zone dictionary
        
    Returns:
        List of {'pointIndex': int, 'value': str} dictionaries
    """
    pointdata_list = zone.get('pointDataList', [])
    if not pointdata_list:
        return []
    
    # Ensure we have the right format
    result = []
    for item in pointdata_list:
        if isinstance(item, dict) and 'pointIndex' in item and 'value' in item:
            result.append({
                'pointIndex': int(item['pointIndex']),
                'value': str(item['value'])
            })
    return result


def compare_pointdata_lists(list1, list2):
    """
    Compare two pointDataList snapshots and return differences.
    
    Args:
        list1: First pointDataList snapshot
        list2: Second pointDataList snapshot
        
    Returns:
        List of differences with format:
        {
            'pointIndex': int,
            'old_value': str or None,
            'new_value': str or None
        }
    """
    # Create dictionaries keyed by pointIndex for efficient lookup
    dict1 = {item['pointIndex']: item['value'] for item in list1}
    dict2 = {item['pointIndex']: item['value'] for item in list2}
    
    # Get all unique pointIndex values
    all_indices = set(dict1.keys()) | set(dict2.keys())
    
    differences = []
    for idx in sorted(all_indices):
        val1 = dict1.get(idx)
        val2 = dict2.get(idx)
        
        # Only include if values differ or one is missing
        if val1 != val2:
            differences.append({
                'pointIndex': idx,
                'old_value': val1,
                'new_value': val2
            })
    
    return differences


def print_pointdata_differences(differences, title):
    """
    Display pointDataList differences in a formatted table.
    
    Args:
        differences: List of difference dictionaries
        title: Title for the results section
    """
    print_subheader(title)
    
    if not differences:
        print(colored("  No differences found", Colors.DIM))
        return
    
    print(f"{'PointIndex':<12} {'Old Value':<15} {'New Value':<15}")
    print("-" * 45)
    
    for diff in differences:
        idx = diff['pointIndex']
        old_val = diff['old_value'] if diff['old_value'] is not None else colored("(missing)", Colors.DIM)
        new_val = diff['new_value'] if diff['new_value'] is not None else colored("(missing)", Colors.DIM)
        
        # Highlight changes
        if diff['old_value'] is None:
            # New point appeared
            print(colored(f"{idx:<12} {old_val:<15} {new_val:<15}", Colors.GREEN))
        elif diff['new_value'] is None:
            # Point disappeared
            print(colored(f"{idx:<12} {old_val:<15} {new_val:<15}", Colors.RED))
        else:
            # Value changed
            print(colored(f"{idx:<12} {old_val:<15} {new_val:<15}", Colors.YELLOW))


def print_summary_table(all_differences):
    """
    Display a summary table showing all pointIndex differences across all test steps.
    
    Args:
        all_differences: Dictionary mapping step names to difference lists
    """
    print_subheader("Summary Table: PointIndex Changes by Step")
    
    # Collect all unique pointIndex values across all steps
    all_point_indices = set()
    for step_name, differences in all_differences.items():
        for diff in differences:
            all_point_indices.add(diff['pointIndex'])
    
    if not all_point_indices:
        print(colored("  No differences found in any step", Colors.DIM))
        return
    
    # Step names in order
    step_names = [
        "Mode ON",
        "Setpoint High + Heat Call",
        "Mode OFF",
        "Mode AUTO",
        "Mode ALL_DAY"
    ]
    
    # Create a mapping of pointIndex -> step -> (old_value, new_value)
    point_data = {}
    for idx in sorted(all_point_indices):
        point_data[idx] = {}
        for step_name in step_names:
            if step_name in all_differences:
                for diff in all_differences[step_name]:
                    if diff['pointIndex'] == idx:
                        point_data[idx][step_name] = (diff['old_value'], diff['new_value'])
                        break
    
    # Print header
    header = f"{'PointIndex':<12}"
    for step_name in step_names:
        # Truncate long step names for table
        short_name = step_name[:20] if len(step_name) > 20 else step_name
        header += f" {short_name:<22}"
    print(header)
    print("-" * len(header))
    
    # Print each pointIndex row
    for idx in sorted(all_point_indices):
        row = f"{idx:<12}"
        for step_name in step_names:
            if step_name in point_data[idx]:
                old_val, new_val = point_data[idx][step_name]
                old_str = old_val if old_val is not None else "-"
                new_str = new_val if new_val is not None else "-"
                change_str = f"{old_str}→{new_str}"
                # Truncate if too long
                if len(change_str) > 20:
                    change_str = change_str[:17] + "..."
                row += f" {change_str:<22}"
            else:
                row += f" {'-':<22}"
        print(row)


def find_zone(homes, zone_query):
    """
    Find a zone by name or ID.
    
    Args:
        homes: List of home dictionaries
        zone_query: Zone name or ID to search for
        
    Returns:
        Tuple of (zone, zone_id) or (None, None) if not found
    """
    query_lower = zone_query.lower()
    for home in homes:
        for zone in home.get('zones', []):
            name = zone_name(zone)
            zone_id = zone.get('zoneid', '')
            if query_lower in name.lower() or zone_query == zone_id:
                return zone, zone_id
    return None, None


def list_all_zones(homes):
    """
    List all zones (both heating and water zones).
    
    Args:
        homes: List of home dictionaries
        
    Returns:
        List of (zone, zone_id, zone_name, is_hotwater) tuples
    """
    all_zones = []
    for home in homes:
        for zone in home.get('zones', []):
            zone_id = zone.get('zoneid', '')
            name = zone_name(zone)
            is_hotwater = zone_is_hotwater(zone)
            all_zones.append((zone, zone_id, name, is_hotwater))
    return all_zones


def refresh_zone_data(ember):
    """
    Force refresh of zone data via HTTP.
    
    Args:
        ember: EphEmber instance
        
    Returns:
        Updated homes list
    """
    # Force refresh by clearing cache
    ember.NextHomeUpdateDaytime = None
    return ember.get_zones()


def wait_for_user_confirmation(prompt, delay_seconds=15):
    """
    Display prompt, wait for user confirmation, then wait for state changes to complete.
    
    Args:
        prompt: Message to display to user
        delay_seconds: Number of seconds to wait after confirmation (default: 15)
    """
    print(f"\n{prompt}")
    input(colored("Press Enter when ready to continue...", Colors.DIM))
    
    # Wait for state changes to complete
    if delay_seconds > 0:
        print(colored(f"\n  Waiting {delay_seconds} seconds for state changes to complete...", Colors.CYAN))
        for remaining in range(delay_seconds, 0, -1):
            print(f"\r  {colored(f'Waiting... {remaining} seconds remaining', Colors.DIM)}", end='', flush=True)
            time.sleep(1)
        print(f"\r  {colored('✓ Wait complete', Colors.GREEN)}" + " " * 15)  # Clear the line


def run_test_sequence(ember, homes):
    """
    Run the complete test sequence for pointIndex analysis.
    
    Args:
        ember: EphEmber instance
        homes: Initial homes list
    """
    print_header("PointIndex Analysis Test Sequence")
    
    # Step 1: Initial Setup - Select test zone
    print_subheader("Step 1: Select Test Zone")
    
    all_zones = list_all_zones(homes)
    if not all_zones:
        print(colored("  Error: No zones found", Colors.RED))
        return
    
    print(f"\n  {colored('Available zones:', Colors.CYAN)}")
    for idx, (zone, zone_id, name, is_hotwater) in enumerate(all_zones, 1):
        zone_type = colored("(Hot Water)", Colors.YELLOW) if is_hotwater else colored("(Heating)", Colors.GREEN)
        print(f"    {idx}. {name} {zone_type} (ID: {zone_id})")
    
    while True:
        try:
            selection = input(f"\n  Enter zone number (1-{len(all_zones)}) or zone name/ID: ").strip()
            
            # Try as number first
            try:
                zone_num = int(selection)
                if 1 <= zone_num <= len(all_zones):
                    test_zone, test_zone_id = all_zones[zone_num - 1][0], all_zones[zone_num - 1][1]
                    test_zone_name = all_zones[zone_num - 1][2]
                    break
            except ValueError:
                pass
            
            # Try as name/ID
            test_zone, test_zone_id = find_zone(homes, selection)
            if test_zone:
                test_zone_name = zone_name(test_zone)
                break
            
            print(colored(f"  Error: Zone '{selection}' not found", Colors.RED))
        except KeyboardInterrupt:
            print(colored("\n  Test cancelled by user", Colors.YELLOW))
            return
    
    is_hotwater = zone_is_hotwater(test_zone)
    zone_type_str = "Hot Water Controller" if is_hotwater else "Heating Zone"
    print(colored(f"\n  Selected zone: {test_zone_name} ({zone_type_str}) (ID: {test_zone_id})", Colors.GREEN))
    
    # Step 2: Baseline Capture (pointDataList1)
    print_subheader("Step 2: Baseline Setup")
    print(f"  Please prepare the test environment:")
    print(f"    a) Make sure all zones are turned off (mode = off)")
    print(f"    b) Make sure {test_zone_name} thermostat has a low setpoint well below room temp (e.g. 15C)")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList1 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Baseline captured ({len(pointDataList1)} points)", Colors.GREEN))
    
    # Store all differences for summary table
    all_differences = {}
    
    # Step 3: Mode ON Test (pointDataList2)
    print_subheader("Step 3: Mode ON Test")
    print(f"  Please perform the following action:")
    print(f"    a) Turn the mode of {test_zone_name} to mode ON")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList2 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Mode ON captured ({len(pointDataList2)} points)", Colors.GREEN))
    
    differences = compare_pointdata_lists(pointDataList1, pointDataList2)
    all_differences["Mode ON"] = differences
    print_pointdata_differences(differences, "'Mode on' test results")
    
    # Step 4: Setpoint High + Heat Call Test (pointDataList3)
    print_subheader("Step 4: Setpoint High + Heat Call Test")
    print(f"  Please perform the following actions:")
    print(f"    a) Set the setpoint of {test_zone_name} to a high setpoint well above room temp (e.g. 25C)")
    print(f"    b) Wait until the heating/boiler has turned on (audible running noise or visible confirmed)")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList3 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Setpoint high + heat call captured ({len(pointDataList3)} points)", Colors.GREEN))
    
    differences = compare_pointdata_lists(pointDataList2, pointDataList3)
    all_differences["Setpoint High + Heat Call"] = differences
    print_pointdata_differences(differences, "'Mode on' and heat call test results")
    
    # Step 5: Mode OFF Test (pointDataList4)
    print_subheader("Step 5: Mode OFF Test")
    print(f"  Please perform the following action:")
    print(f"    a) Turn the mode of {test_zone_name} to mode OFF")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList4 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Mode OFF captured ({len(pointDataList4)} points)", Colors.GREEN))
    
    differences = compare_pointdata_lists(pointDataList3, pointDataList4)
    all_differences["Mode OFF"] = differences
    print_pointdata_differences(differences, "'Mode off' test results")
    
    # Step 6: Mode AUTO Test (pointDataList5)
    print_subheader("Step 6: Mode AUTO Test")
    print(f"  Please perform the following action:")
    print(f"    a) Turn the mode of {test_zone_name} to mode AUTO")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList5 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Mode AUTO captured ({len(pointDataList5)} points)", Colors.GREEN))
    
    differences = compare_pointdata_lists(pointDataList4, pointDataList5)
    all_differences["Mode AUTO"] = differences
    print_pointdata_differences(differences, "'Mode auto' and heat call test results")
    
    # Step 7: Mode ALL_DAY Test (pointDataList6)
    print_subheader("Step 7: Mode ALL_DAY Test")
    print(f"  Please perform the following action:")
    print(f"    a) Turn the mode of {test_zone_name} to mode ALL_DAY")
    
    wait_for_user_confirmation("")
    
    print("  Refreshing zone data...")
    homes = refresh_zone_data(ember)
    test_zone, _ = find_zone(homes, test_zone_id)
    if not test_zone:
        print(colored("  Error: Could not find test zone after refresh", Colors.RED))
        return
    
    pointDataList6 = extract_pointdata_list(test_zone)
    print(colored(f"  ✓ Mode ALL_DAY captured ({len(pointDataList6)} points)", Colors.GREEN))
    
    differences = compare_pointdata_lists(pointDataList5, pointDataList6)
    all_differences["Mode ALL_DAY"] = differences
    print_pointdata_differences(differences, "'Mode all day' and heat call test results")
    
    # Step 8: Completion with Summary Table
    print_header("Test Complete")
    print(colored("  All test steps completed successfully!", Colors.GREEN))
    print(f"\n  Summary:")
    print(f"    - Baseline: {len(pointDataList1)} points")
    print(f"    - Mode ON: {len(pointDataList2)} points")
    print(f"    - Setpoint High: {len(pointDataList3)} points")
    print(f"    - Mode OFF: {len(pointDataList4)} points")
    print(f"    - Mode AUTO: {len(pointDataList5)} points")
    print(f"    - Mode ALL_DAY: {len(pointDataList6)} points")
    
    # Print summary table
    print_summary_table(all_differences)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog='testpointindex1.py',
        description='PointIndex Analysis Test Program for pyephember2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python testpointindex1.py --email user@example.com
  python testpointindex1.py --email user@example.com --debug
        """
    )
    
    # Authentication
    parser.add_argument("--email", type=str, required=True,
                        help="Email address for your EPH account")
    parser.add_argument('--password', type=str, default="",
                        help="Password (will prompt if not provided)")
    parser.add_argument('--debug', action='store_true',
                        help="Enable debug output")
    
    args = parser.parse_args()
    
    # Setup logging
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')
    
    # Get password
    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
    
    print_header("Connecting to EPH Controls Ember")
    print(f"  Email: {args.email}")
    
    try:
        # Create ember instance
        ember = EphEmber(args.email, password)
        print(colored("  ✓ Login successful", Colors.GREEN))
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
    
    # Run test sequence
    try:
        run_test_sequence(ember, homes)
    except KeyboardInterrupt:
        print(colored("\n\n  Test interrupted by user", Colors.YELLOW))
        sys.exit(1)
    except Exception as e:
        print(colored(f"\n  ✗ Error during test: {e}", Colors.RED))
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
