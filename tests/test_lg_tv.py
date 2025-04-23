#!/usr/bin/env python3
"""
Test script for LG TV device.

This script initializes an LG TV device using a provided configuration file
and reports which controls were successfully initialized.

Usage:
    python test_lg_tv.py path/to/config.json
"""

import asyncio
import argparse
import json
import logging
import sys
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


async def test_control_functionality(tv: LgTv) -> Dict[str, Dict[str, Any]]:
    """
    Test if each control is not only initialized but also functional.
    This detects controls that are available but might report missing permissions.
    
    Args:
        tv: Initialized LG TV device instance
        
    Returns:
        Dictionary with control status information
    """
    logger = logging.getLogger("test_control_functionality")
    results = {}
    
    # Test Media Control
    if tv.media is not None:
        logger.info("Testing Media Control functionality...")
        media_results = {}
        
        # Test volume get operation
        try:
            volume_info = await tv.media.get_volume()  # type: ignore
            media_results["get_volume"] = {
                "functional": True,
                "result": volume_info
            }
        except Exception as e:
            media_results["get_volume"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Media Control get_volume test failed: {str(e)}")
            
        # Test volume mute status (often requires separate permission)
        try:
            mute_status = await tv.media.get_mute()  # type: ignore
            media_results["get_mute"] = {
                "functional": True,
                "result": mute_status
            }
        except Exception as e:
            media_results["get_mute"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Media Control get_mute test failed: {str(e)}")
            
        # Test play status (may require additional rights)
        try:
            play_state = await tv.media.get_status()  # type: ignore
            media_results["get_status"] = {
                "functional": True,
                "result": play_state
            }
        except Exception as e:
            media_results["get_status"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Media Control get_status test failed: {str(e)}")
        
        results["Media Control"] = media_results
    
    # Test System Control
    if tv.system is not None:
        logger.info("Testing System Control functionality...")
        system_results = {}
        
        # Test system info
        try:
            system_info = await tv.system.info()  # type: ignore
            system_results["info"] = {
                "functional": True,
                "result": system_info
            }
        except Exception as e:
            system_results["info"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"System Control info test failed: {str(e)}")
            
        # Test power state (might need specific access rights)
        try:
            power_state = await tv.system.power_state()  # type: ignore
            system_results["power_state"] = {
                "functional": True,
                "result": power_state
            }
        except Exception as e:
            system_results["power_state"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"System Control power_state test failed: {str(e)}")
            
        # Test notify (might need specific access rights)
        try:
            # Just a test message that won't be displayed for long
            notify_result = await tv.system.notify("Test notification from Bridge")  # type: ignore
            system_results["notify"] = {
                "functional": True,
                "result": notify_result
            }
        except Exception as e:
            system_results["notify"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"System Control notify test failed: {str(e)}")
        
        results["System Control"] = system_results
    
    # Test Application Control
    if tv.app is not None:
        logger.info("Testing Application Control functionality...")
        app_results = {}
        
        # Define apps_list as None initially
        apps_list = None
        
        # Test list apps
        try:
            apps_list = await tv.app.list_apps()  # type: ignore
            app_results["list_apps"] = {
                "functional": True,
                "count": len(apps_list) if apps_list else 0
            }
        except Exception as e:
            app_results["list_apps"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Application Control list_apps test failed: {str(e)}")
        
        # Test get current app - requires additional permissions
        try:
            current_app = await tv.app.get_current()  # type: ignore
            app_results["get_current"] = {
                "functional": True,
                "result": current_app
            }
        except Exception as e:
            app_results["get_current"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Application Control get_current test failed: {str(e)}")
            
        # Test get app info - may require specific permissions
        # Only try if apps_list was successfully retrieved and has items
        if apps_list and len(apps_list) > 0:
            try:
                # Try to get info for the first app in the list
                first_app = apps_list[0]
                app_id = first_app.id if hasattr(first_app, 'id') else first_app
                app_info = await tv.app.get_app_info(app_id)  # type: ignore
                app_results["get_app_info"] = {
                    "functional": True,
                    "result": app_info
                }
            except Exception as e:
                app_results["get_app_info"] = {
                    "functional": False,
                    "error": str(e)
                }
                logger.warning(f"Application Control get_app_info test failed: {str(e)}")
        
        results["Application Control"] = app_results
    
    # Test TV Control
    if tv.tv_control is not None:
        logger.info("Testing TV Control functionality...")
        tv_control_results = {}
        
        # Test get current channel (requires TV tuner rights)
        try:
            channel_info = await tv.tv_control.get_current_channel()  # type: ignore
            tv_control_results["get_current_channel"] = {
                "functional": True,
                "result": channel_info
            }
        except Exception as e:
            tv_control_results["get_current_channel"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"TV Control get_current_channel test failed: {str(e)}")
            
        # Test get channel list (requires TV tuner rights)
        try:
            channel_list = await tv.tv_control.get_channel_list()  # type: ignore
            tv_control_results["get_channel_list"] = {
                "functional": True,
                "count": len(channel_list) if channel_list else 0
            }
        except Exception as e:
            tv_control_results["get_channel_list"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"TV Control get_channel_list test failed: {str(e)}")
            
        results["TV Control"] = tv_control_results
    
    # Test Input Control
    if tv.input_control is not None:
        logger.info("Testing Input Control functionality...")
        input_results = {}
        
        # Check if input connection can be established
        try:
            await tv.input_control.connect_input()
            input_results["connect_input"] = {
                "functional": True
            }
        except Exception as e:
            input_results["connect_input"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Input Control connect_input test failed: {str(e)}")
            
        # Test remote key functionality if available
        try:
            # Just test if the method exists and can be called
            has_method = hasattr(tv.input_control, "send_remote_key")
            if has_method:
                input_results["has_remote_key"] = {
                    "functional": True
                }
            else:
                input_results["has_remote_key"] = {
                    "functional": False,
                    "error": "Method not available"
                }
        except Exception as e:
            input_results["has_remote_key"] = {
                "functional": False,
                "error": str(e)
            }
            
        results["Input Control"] = input_results
    
    # Test Source Control
    if tv.source_control is not None:
        logger.info("Testing Source Control functionality...")
        source_results = {}
        
        # Test list sources
        try:
            sources = await tv.source_control.list_sources()  # type: ignore
            source_results["list_sources"] = {
                "functional": True,
                "count": len(sources) if sources else 0
            }
        except Exception as e:
            source_results["list_sources"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Source Control list_sources test failed: {str(e)}")
            
        # Test get current input
        try:
            current_input = await tv.source_control.get_current_input()  # type: ignore
            source_results["get_current_input"] = {
                "functional": True,
                "result": current_input
            }
        except Exception as e:
            source_results["get_current_input"] = {
                "functional": False,
                "error": str(e)
            }
            logger.warning(f"Source Control get_current_input test failed: {str(e)}")
            
        results["Source Control"] = source_results
    
    return results


async def test_lg_tv(config_path: str) -> None:
    """
    Initialize an LG TV device and test its functionality.
    
    Args:
        config_path: Path to the configuration file
    """
    logger = logging.getLogger("test_lg_tv")
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)
        
        # Create LG TV device instance
        logger.info(f"Initializing LG TV device: {config.get('device_name', 'unknown')}")
        tv = LgTv(config)
        
        # Set up the device
        logger.info("Setting up the device...")
        setup_success = await tv.setup()
        
        if not setup_success:
            logger.error("Device setup failed")
            return
            
        # Report device state
        logger.info("Device setup completed successfully")
        logger.info(f"Device ID: {tv.get_id()}")
        logger.info(f"Device Name: {tv.get_name()}")
        
        # Check if connected
        connected = tv.state.get("connected", False)
        logger.info(f"Connected: {connected}")
        
        if not connected:
            logger.warning("Device is not connected. Some controls may not be available.")
        
        # Report initialized controls
        logger.info("--- Initialized Controls ---")
        controls_status = {
            "Media Control": tv.media is not None,
            "System Control": tv.system is not None,
            "Application Control": tv.app is not None,
            "TV Control": tv.tv_control is not None,
            "Input Control": tv.input_control is not None,
            "Source Control": tv.source_control is not None
        }
        
        for control_name, is_available in controls_status.items():
            status = "Available" if is_available else "Not Available"
            logger.info(f"{control_name}: {status}")
        
        # Test the functionality of each control
        if connected:
            logger.info("\n--- Control Functionality Testing ---")
            control_test_results = await test_control_functionality(tv)
            
            # Display the results
            for control_name, operations in control_test_results.items():
                logger.info(f"\n{control_name} Operations:")
                for operation, status in operations.items():
                    if status.get("functional", False):
                        logger.info(f"  - {operation}: ✓ Functional")
                    else:
                        error_msg = status.get("error", "Unknown error")
                        if "permission" in error_msg.lower() or "rights" in error_msg.lower() or "access" in error_msg.lower() or "not allowed" in error_msg.lower():
                            logger.warning(f"  - {operation}: ✗ Missing permissions: {error_msg}")
                        else:
                            logger.warning(f"  - {operation}: ✗ Failed: {error_msg}")
            
            # Overall results summary
            logger.info("\n--- Control Permissions Summary ---")
            permissions_summary = {}
            for control_name, operations in control_test_results.items():
                functional_count = sum(1 for op in operations.values() if op.get("functional", False))
                total_operations = len(operations)
                permissions_summary[control_name] = {
                    "functional": functional_count,
                    "total": total_operations,
                    "percentage": round((functional_count / total_operations) * 100) if total_operations > 0 else 0
                }
                
            for control_name, stats in permissions_summary.items():
                logger.info(f"{control_name}: {stats['functional']}/{stats['total']} operations available ({stats['percentage']}%)")
        
        # Report available commands
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
        
        # Clean up
        logger.info("Shutting down the device...")
        await tv.shutdown()
        logger.info("Test completed")
        
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in configuration file: {config_path}")
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")


def main() -> None:
    """Parse command line arguments and run the test."""
    parser = argparse.ArgumentParser(description="Test LG TV device functionality")
    parser.add_argument("config_file", help="Path to the configuration file")
    args = parser.parse_args()
    
    setup_logging()
    asyncio.run(test_lg_tv(args.config_file))


if __name__ == "__main__":
    main() 