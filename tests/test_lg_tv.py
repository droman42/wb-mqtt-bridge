#!/usr/bin/env python3
"""
Test script for LG TV device.

This script initializes an LG TV device using a provided configuration file
and tests the complete initialization process, including automatic Wake-on-LAN
functionality if the TV is not initially responsive.

Usage:
    python test_lg_tv.py path/to/config.json
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Add parent directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from devices.lg_tv import LgTv


def setup_logging() -> None:
    """Configure logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load device configuration from a JSON file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dictionary containing the device configuration
    
    Raises:
        FileNotFoundError: If the config file doesn't exist
        json.JSONDecodeError: If the config file contains invalid JSON
    """
    with open(config_path, 'r') as f:
        return json.load(f)


async def test_natural_initialization(tv: LgTv) -> bool:
    """
    Test the TV's natural initialization process, including Wake-on-LAN if needed.
    This tests the device's ability to automatically wake and connect to the TV.
    
    Args:
        tv: LG TV device to test
        
    Returns:
        True if initialization succeeded, False otherwise
    """
    logger = logging.getLogger("test_natural_initialization")
    
    logger.info("Testing TV natural initialization process...")
    
    # Verify MAC address is properly configured
    mac_address = tv.state.get("mac_address")
    if not mac_address:
        logger.warning("MAC address is not configured. Wake-on-LAN will not work.")
    else:
        logger.info(f"MAC address is configured: {mac_address}")
    
    # First, check if the TV is already connected
    if tv.state.get("connected", False):
        logger.info("TV is already connected. Testing reconnection...")
        
        # Disconnect first to test reconnection
        await tv.shutdown()
        logger.info("Disconnected from TV. Waiting 2 seconds before reconnecting...")
        await asyncio.sleep(2)
    
    # Now try to connect - this should trigger the full connection process
    # including Wake-on-LAN if the TV is off
    logger.info("Attempting to connect to TV...")
    start_time = time.time()
    connection_result = await tv.connect()
    elapsed_time = time.time() - start_time
    
    if connection_result:
        logger.info(f"Successfully connected to TV in {elapsed_time:.2f} seconds")
        
        # Check if we have control interfaces
        control_status = {
            "Media Control": tv.media is not None,
            "System Control": tv.system is not None,
            "Application Control": tv.app is not None,
            "TV Control": tv.tv_control is not None,
            "Input Control": tv.input_control is not None,
            "Source Control": tv.source_control is not None
        }
        
        for control_name, available in control_status.items():
            logger.info(f"{control_name}: {'Available' if available else 'Not Available'}")
        
        # Try to get TV state information
        logger.info("Requesting current TV state...")
        await tv._update_tv_state()
        
        logger.info(f"Current state: Power={tv.state.get('power', 'unknown')}, "
                   f"Volume={tv.state.get('volume', 'unknown')}, "
                   f"Muted={tv.state.get('mute', 'unknown')}, "
                   f"Current app={tv.state.get('current_app', 'unknown')}, "
                   f"Input source={tv.state.get('input_source', 'unknown')}")
        
        # Check if Wake-on-LAN was attempted
        last_command = tv.state.get("last_command")
        if last_command:
            if hasattr(last_command, 'action'):
                # It's a pydantic model
                wake_on_lan_attempted = last_command.action == "wake_on_lan"
            elif isinstance(last_command, dict) and "action" in last_command:
                # Fallback for dict format
                wake_on_lan_attempted = last_command["action"] == "wake_on_lan"
            elif isinstance(last_command, str):
                # Fallback for string format
                wake_on_lan_attempted = last_command in ["wake_on_lan", "power_on_wol"]
            else:
                wake_on_lan_attempted = False
            
            if wake_on_lan_attempted:
                logger.info("Wake-on-LAN was attempted during initialization")
            else:
                logger.warning("Wake-on-LAN was not attempted during initialization")
        else:
            logger.warning("No last_command recorded during initialization")
        
        return True
    else:
        logger.error(f"Failed to connect to TV after {elapsed_time:.2f} seconds")
        logger.error(f"Error: {tv.state.get('error', 'Unknown error')}")
        
        # Check if the error message contains "no response" which should trigger WoL
        error_msg = tv.state.get("error", "")
        if "no response" in error_msg.lower():
            logger.info("Error contains 'no response', which should trigger WoL")
        else:
            logger.warning(f"Error message '{error_msg}' doesn't contain 'no response', which might be why WoL wasn't triggered")
        
        return False


async def test_direct_power_on(tv: LgTv) -> bool:
    """
    Test direct power-on functionality, which should use WoL if the TV is off.
    
    Args:
        tv: LG TV device to test
        
    Returns:
        True if power-on was successful, False otherwise
    """
    logger = logging.getLogger("test_direct_power_on")
    
    logger.info("Testing direct power-on functionality...")
    
    # Verify MAC address is properly configured
    mac_address = tv.state.get("mac_address")
    if not mac_address:
        logger.warning("MAC address is not configured. Wake-on-LAN will not work.")
    else:
        logger.info(f"MAC address is configured: {mac_address}")
    
    # Try power on - this should use WoL if needed
    logger.info("Calling power_on method directly...")
    start_time = time.time()
    result = await tv.power_on()
    elapsed_time = time.time() - start_time
    
    logger.info(f"Power-on completed in {elapsed_time:.2f} seconds with result: {result}")
    logger.info(f"Last command: {tv.state.get('last_command')}")
    
    # Check if Wake-on-LAN was used
    last_command = tv.state.get("last_command")
    if last_command:
        if hasattr(last_command, 'action'):
            # It's a pydantic model
            wol_used = last_command.action in ["wake_on_lan", "power_on_wol"]
        elif isinstance(last_command, dict) and "action" in last_command:
            # Fallback for dict format
            wol_used = last_command["action"] in ["wake_on_lan", "power_on_wol"]
        elif isinstance(last_command, str):
            # Fallback for string format
            wol_used = last_command in ["wake_on_lan", "power_on_wol"]
        else:
            wol_used = False
        
        if wol_used:
            logger.info("Wake-on-LAN was used during power-on")
        else:
            logger.warning(f"Wake-on-LAN was not used during power-on. Last command: {last_command}")
    else:
        logger.warning("No last_command recorded during power-on")
    
    # At this point, the power_on method should have already attempted to connect if successful
    # But we'll verify the connection state to confirm everything worked
    if result:
        if tv.state.get("connected", False):
            logger.info("Successfully connected to TV after power-on")
            return True
        else:
            logger.warning("TV powered on but not connected. Will attempt to connect...")
            connect_result = await tv.connect()
            if connect_result:
                logger.info("Successfully connected to TV after explicit connect call")
                return True
            else:
                logger.error(f"Failed to connect to TV after power-on. Error: {tv.state.get('error')}")
                return False
    
    return result


async def test_power_functions(tv: LgTv) -> Dict[str, Any]:
    """
    Test power-related functionality of the TV.
    
    Args:
        tv: Initialized LG TV device instance
        
    Returns:
        Dictionary with test results
    """
    logger = logging.getLogger("test_power_functions")
    results = {}
    
    # Skip tests if TV is not connected
    if not tv.state.get("connected", False):
        logger.warning("TV is not connected. Skipping power function tests.")
        return {"error": "TV not connected"}
    
    # Test power_off and power_on sequence
    try:
        logger.info("Testing power off...")
        power_off_result = await tv.power_off()
        results["power_off"] = {
            "success": power_off_result,
            "state_after": tv.state.get("power"),
            "last_command": tv.state.get("last_command")
        }
        
        logger.info(f"Power off result: {power_off_result}")
        
        # Wait a moment between power operations
        await asyncio.sleep(5)
        
        logger.info("Testing power on...")
        power_on_result = await tv.power_on()
        results["power_on"] = {
            "success": power_on_result,
            "state_after": tv.state.get("power"),
            "last_command": tv.state.get("last_command")
        }
        
        logger.info(f"Power on result: {power_on_result}")
        
        # If power on succeeded, wait for the TV to fully boot
        if power_on_result:
            logger.info("Waiting for TV to complete boot process...")
            await asyncio.sleep(10)
            
            # Test reconnect after power cycle
            logger.info("Testing connection after power cycle...")
            reconnect_result = await tv.connect()
            results["reconnect_after_power_cycle"] = {
                "success": reconnect_result,
                "connected": tv.state.get("connected"),
                "error": tv.state.get("error")
            }
    except Exception as e:
        logger.error(f"Error testing power functions: {str(e)}")
        results["error"] = str(e)
    
    return results


async def test_lg_tv(config_path: str) -> None:
    """
    Main test function for LG TV device.
    
    Args:
        config_path: Path to the configuration file
    """
    logger = logging.getLogger("test_lg_tv")
    
    try:
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)
        
        # Get the device name from the config
        device_name = config.get("device_name", "Unknown TV")
        logger.info(f"Initializing LG TV device: {device_name}")
        
        # Create TV instance
        tv = LgTv(config, mqtt_client=None)
        
        logger.info("Setting up the device...")
        setup_success = await tv.setup()
        
        logger.info("Device setup completed successfully" if setup_success else "Device setup failed")
            
        # Display device information
        logger.info(f"Device ID: {tv.get_id()}")
        logger.info(f"Device Name: {tv.get_name()}")
        logger.info(f"Connected: {tv.state.get('connected', False)}")
        
        # If not connected, first test direct power-on functionality
        if not tv.state.get("connected", False):
            logger.info("\n--- Testing Direct Power-On (should use WoL) ---")
            power_on_result = await test_direct_power_on(tv)
            logger.info(f"Direct power-on test {'succeeded' if power_on_result else 'failed'}")
            
            # If still not connected, test natural initialization
            if not tv.state.get("connected", False):
                logger.warning("Device is still not connected. Testing natural initialization process...")
                init_result = await test_natural_initialization(tv)
                logger.info(f"Natural initialization {'succeeded' if init_result else 'failed'}")
        
        # Report on initialized controls
        logger.info("--- Initialized Controls ---")
        logger.info(f"Media Control: {'Available' if tv.media else 'Not Available'}")
        logger.info(f"System Control: {'Available' if tv.system else 'Not Available'}")
        logger.info(f"Application Control: {'Available' if tv.app else 'Not Available'}")
        logger.info(f"TV Control: {'Available' if tv.tv_control else 'Not Available'}")
        logger.info(f"Input Control: {'Available' if tv.input_control else 'Not Available'}")
        logger.info(f"Source Control: {'Available' if tv.source_control else 'Not Available'}")
        
        # Display available commands
        logger.info("\n--- Available Commands ---")
        for cmd_name, cmd_config in tv.get_available_commands().items():
            logger.info(f"Command: {cmd_name}")
            if "description" in cmd_config:
                logger.info(f"  Description: {cmd_config['description']}")
            if "topic" in cmd_config:
                logger.info(f"  Topic: {cmd_config['topic']}")
            if "group" in cmd_config:
                logger.info(f"  Group: {cmd_config['group']}")
            logger.info("---")
        
        # Test power functions if TV is connected
        if tv.state.get("connected", False):
            logger.info("\n--- Testing Power Functions ---")
            power_results = await test_power_functions(tv)
            logger.info(f"Power function tests completed: {power_results}")
        
        # Shutdown the device
        logger.info("Shutting down the device...")
        await tv.shutdown()
        
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in configuration file: {config_path}")
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
    
    logger.info("Test completed")


def main() -> None:
    """Main entry point for the script."""
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Test LG TV device")
    parser.add_argument("config", help="Path to device configuration JSON file")
    args = parser.parse_args()
    
    # Set up logging
    setup_logging()
    
    # Run the test
    asyncio.run(test_lg_tv(args.config))


if __name__ == "__main__":
    main() 