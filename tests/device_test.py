#!/usr/bin/env python3
"""
Device Function Test Script

This script automates testing of device functions by executing commands via REST API or MQTT.
It loads a device configuration, tests all available commands, and logs the results.

Usage:
    python device_test.py --config <path> --mode <rest|mqtt|both> [options]

Options:
    --config <path>           Path to device config file (e.g., config/devices/device1.json)
    --mode <rest|mqtt|both>   Interface to use for command execution
    --wait <seconds>          Time to wait between commands (default: 1)
    --prompt                  Prompt for parameter values (default: use values from schema)
    --include <cmd1,cmd2,...> Only include these commands
    --exclude <cmd1,cmd2,...> Exclude these commands
"""

import os
import sys
import json
import time
import asyncio
import argparse
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path
from pydantic import BaseModel
import inspect

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config_manager import ConfigManager
from app.device_manager import DeviceManager
from app.mqtt_client import MQTTClient
from devices.base_device import BaseDevice

logger = logging.getLogger("device_test")

class TestResults:
    """Class to store and summarize test results."""
    
    def __init__(self):
        self.total_commands = 0
        self.successful_commands = 0
        self.failed_commands = []
        self.command_durations = {}
        self.start_time = time.time()
    
    def record_command_result(self, command: str, success: bool, duration: float, error: Optional[str] = None):
        """Record the result of a command execution."""
        self.total_commands += 1
        self.command_durations[command] = duration
        
        if success:
            self.successful_commands += 1
        else:
            self.failed_commands.append((command, error))
    
    def print_summary(self):
        """Print a summary of the test results."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "="*60)
        print(" DEVICE TEST SUMMARY ".center(60, "="))
        print("="*60)
        
        # Command statistics
        print(f"Total commands tested: {self.total_commands}")
        print(f"Successful commands: {self.successful_commands}")
        print(f"Failed commands: {len(self.failed_commands)}")
        
        if self.total_commands > 0:
            success_rate = (self.successful_commands / self.total_commands) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        # Timing information
        print(f"Total test duration: {total_duration:.2f} seconds")
        
        if self.command_durations:
            avg_duration = sum(self.command_durations.values()) / len(self.command_durations)
            slowest_cmd = max(self.command_durations.items(), key=lambda x: x[1])
            fastest_cmd = min(self.command_durations.items(), key=lambda x: x[1])
            
            print(f"Average command duration: {avg_duration:.2f} seconds")
            print(f"Slowest command: {slowest_cmd[0]} ({slowest_cmd[1]:.2f} seconds)")
            print(f"Fastest command: {fastest_cmd[0]} ({fastest_cmd[1]:.2f} seconds)")
        
        # Failed commands
        if self.failed_commands:
            print("\nFailed commands:")
            for cmd, error in self.failed_commands:
                print(f"  - {cmd}: {error}")
        
        print("="*60)


class DeviceTester:
    """Class to test device functionality."""
    
    def __init__(self, config_path: str, mode: str, wait_time: float, prompt: bool,
                 include_commands: Optional[Set[str]] = None, exclude_commands: Optional[Set[str]] = None):
        self.config_path = config_path
        self.mode = mode
        self.wait_time = wait_time
        self.prompt = prompt
        self.include_commands = include_commands
        self.exclude_commands = exclude_commands
        
        self.config_manager = ConfigManager()
        self.mqtt_client = None
        self.device_manager = None
        self.device = None
        self.device_config = None
        self.device_id = None
        
        self.command_groups = {}
        self.power_on_command = None
        self.power_off_command = None
        
        self.results = TestResults()
    
    async def setup(self):
        """Set up the test environment."""
        logger.info(f"Setting up test environment for config: {self.config_path}")
        
        # Load device configuration
        with open(self.config_path, 'r') as f:
            device_config = json.load(f)
        
        # Extract device ID from filename if not in config
        if 'device_id' not in device_config:
            device_id = os.path.basename(self.config_path).split('.')[0]
            device_config['device_id'] = device_id
        
        self.device_id = device_config['device_id']
        
        # Get device class from system.json
        system_config = self.config_manager.get_system_config()
        
        # Find device class info from system config
        device_info = None
        for dev_id, info in system_config.devices.items():
            config_file = info.get('config_file', '')
            if os.path.basename(self.config_path) == config_file or self.device_id == dev_id:
                device_info = info
                # Use the ID from system.json if found
                self.device_id = dev_id
                break
        
        if not device_info:
            raise ValueError(f"Device with config {self.config_path} not found in system configuration")
        
        device_class_name = device_info.get('class')
        if not device_class_name:
            raise ValueError(f"No class specified for device {self.device_id}")
        
        # Add class name to config
        device_config['device_class'] = device_class_name
        self.device_config = device_config
        
        # Set up MQTT client if needed
        if self.mode in ['mqtt', 'both']:
            mqtt_config = system_config.mqtt_broker
            self.mqtt_client = MQTTClient(mqtt_config.model_dump())
            await self.mqtt_client.connect()
            logger.info(f"Connected to MQTT broker at {mqtt_config.host}:{mqtt_config.port}")
        
        # Set up device manager and load device modules
        self.device_manager = DeviceManager(mqtt_client=self.mqtt_client)
        await self.device_manager.load_device_modules()
        
        # Find device class
        device_class = None
        for name, cls in self.device_manager.device_classes.items():
            if name == device_class_name:
                device_class = cls
                break
        
        if not device_class:
            raise ValueError(f"Device class {device_class_name} not found")
        
        # Create device instance
        self.device = device_class(device_config, self.mqtt_client)
        await self.device.setup()
        logger.info(f"Device {self.device_id} initialized successfully")
        
        # Organize commands into groups
        self._organize_commands()
    
    def _organize_commands(self):
        """Organize commands into groups and identify power commands."""
        commands = self.device.get_available_commands()
        
        # Group commands
        self.command_groups = {}
        for cmd_name, cmd_config in commands.items():
            # Skip if command should be excluded
            if self.exclude_commands and cmd_name in self.exclude_commands:
                continue
                
            # Skip if we're only including specific commands and this isn't one
            if self.include_commands and cmd_name not in self.include_commands:
                continue
                
            group = cmd_config.get('group', 'default')
            if group not in self.command_groups:
                self.command_groups[group] = []
            
            self.command_groups[group].append((cmd_name, cmd_config))
        
        # Identify power commands
        power_commands = self.command_groups.get('power', [])
        if not power_commands:
            # Look for commands with "power" in their name
            for group_name, cmds in self.command_groups.items():
                for cmd_name, _ in cmds:
                    if 'power' in cmd_name.lower():
                        if 'on' in cmd_name.lower():
                            self.power_on_command = cmd_name
                        elif 'off' in cmd_name.lower():
                            self.power_off_command = cmd_name
        else:
            # Use the first power command for both on/off if only one exists
            if len(power_commands) == 1:
                self.power_on_command = power_commands[0][0]
                self.power_off_command = power_commands[0][0]
            else:
                # Try to find specific on/off commands
                for cmd_name, _ in power_commands:
                    if 'on' in cmd_name.lower():
                        self.power_on_command = cmd_name
                    elif 'off' in cmd_name.lower():
                        self.power_off_command = cmd_name
                
                # If not found, use the first power command for both
                if not self.power_on_command and power_commands:
                    self.power_on_command = power_commands[0][0]
                if not self.power_off_command and power_commands:
                    self.power_off_command = power_commands[0][0]
        
        logger.info(f"Organized commands into {len(self.command_groups)} groups")
        logger.info(f"Power ON command: {self.power_on_command}")
        logger.info(f"Power OFF command: {self.power_off_command}")
    
    async def _get_parameter_values(self, action: str, required_params: Dict[str, Any]) -> Dict[str, Any]:
        """Get parameter values either by prompting or using defaults."""
        param_values = {}
        
        if not required_params:
            return param_values
        
        # Get parameter schema from action handler
        handler = getattr(self.device, f"_{action}", None) or getattr(self.device, action, None)
        param_schemas = {}
        
        if handler:
            sig = inspect.signature(handler)
            for param_name, param in sig.parameters.items():
                if param_name not in ['self', 'args', 'kwargs'] and param.annotation != inspect.Parameter.empty:
                    param_schemas[param_name] = param.annotation
        
        for param_name, param_type in param_schemas.items():
            if param_name in required_params:
                default_value = required_params[param_name]
                
                if self.prompt:
                    # Prompt for parameter value
                    param_desc = f"{param_name} ({param_type.__name__})"
                    if default_value is not None:
                        user_input = input(f"Enter value for {param_desc} [{default_value}]: ")
                        if not user_input:
                            param_values[param_name] = default_value
                        else:
                            # Try to convert to the right type
                            try:
                                if param_type == bool:
                                    param_values[param_name] = user_input.lower() in ['true', 'yes', 'y', '1']
                                else:
                                    param_values[param_name] = param_type(user_input)
                            except ValueError:
                                logger.warning(f"Invalid input for {param_name}, using default")
                                param_values[param_name] = default_value
                    else:
                        user_input = input(f"Enter value for {param_desc}: ")
                        if user_input:
                            try:
                                if param_type == bool:
                                    param_values[param_name] = user_input.lower() in ['true', 'yes', 'y', '1']
                                else:
                                    param_values[param_name] = param_type(user_input)
                            except ValueError:
                                logger.warning(f"Invalid input for {param_name}")
                else:
                    # Use default value
                    if default_value is not None:
                        param_values[param_name] = default_value
        
        return param_values
    
    async def _execute_command(self, command: str, command_config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Execute a command and return success status and error message."""
        action = command_config.get('action', command)
        params = command_config.get('params', {})
        
        logger.info(f"Executing command: {command} (action: {action})")
        
        # Get parameter values
        param_values = await self._get_parameter_values(action, params)
        
        # Execute command via appropriate interface
        start_time = time.time()
        error = None
        
        try:
            if self.mode == 'rest':
                # Use the device's execute_action method for REST-like interface
                result = await self.device.execute_action(action, param_values)
                success = result.get('success', False)
                if not success:
                    error = result.get('error', 'Unknown error')
            
            elif self.mode == 'mqtt':
                # Use the device's MQTT topic if available
                topic = command_config.get('topic')
                if not topic:
                    logger.warning(f"No MQTT topic found for command {command}")
                    return False, "No MQTT topic configured"
                
                # Convert parameters to MQTT payload
                payload = json.dumps({"action": action, "params": param_values})
                await self.mqtt_client.publish(topic, payload)
                
                # Wait for device state update
                await asyncio.sleep(self.wait_time)
                
                # Check device state for success
                device_state = self.device.get_current_state()
                last_command = device_state.get('last_command')
                
                # Simple check - if the last command matches what we executed, consider it successful
                success = last_command and (
                    (isinstance(last_command, dict) and last_command.get('action') == action) or
                    last_command == action
                )
                if not success:
                    error = "Command not reflected in device state"
            
            else:  # mode == 'both'
                # Execute via REST first
                rest_result = await self.device.execute_action(action, param_values)
                rest_success = rest_result.get('success', False)
                
                # Wait between commands
                await asyncio.sleep(self.wait_time)
                
                # Then via MQTT
                topic = command_config.get('topic')
                if topic:
                    payload = json.dumps({"action": action, "params": param_values})
                    await self.mqtt_client.publish(topic, payload)
                    
                    # Wait for device state update
                    await asyncio.sleep(self.wait_time)
                    
                    # Update device state
                    device_state = self.device.get_current_state()
                    
                    # Consider successful if either interface worked
                    mqtt_success = 'error' not in device_state or not device_state['error']
                    success = rest_success or mqtt_success
                    
                    if not success:
                        error = rest_result.get('error') or device_state.get('error', 'Unknown error')
                else:
                    # If no MQTT topic, just use REST result
                    success = rest_success
                    if not success:
                        error = rest_result.get('error', 'Unknown error')
        
        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"Error executing command {command}: {error}")
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log the outcome
        if success:
            logger.info(f"Command {command} succeeded in {duration:.2f} seconds")
        else:
            logger.error(f"Command {command} failed in {duration:.2f} seconds: {error}")
        
        # Log device state after command
        device_state = self.device.get_current_state()
        logger.info(f"Device state after command: {json.dumps(device_state, default=str)}")
        
        # Record result
        self.results.record_command_result(command, success, duration, error)
        
        # Wait between commands
        await asyncio.sleep(self.wait_time)
        
        return success, error
    
    async def run_tests(self):
        """Run all tests in the appropriate order."""
        logger.info("Starting device function tests")
        
        # Execute power ON command first
        if self.power_on_command:
            cmd_config = None
            for group, cmds in self.command_groups.items():
                for cmd_name, cfg in cmds:
                    if cmd_name == self.power_on_command:
                        cmd_config = cfg
                        break
                if cmd_config:
                    break
            
            if cmd_config:
                logger.info("Executing power ON command")
                success, error = await self._execute_command(self.power_on_command, cmd_config)
                if not success:
                    logger.error(f"Power ON command failed: {error}")
                    logger.error("Cannot proceed with tests, exiting")
                    return
            else:
                logger.warning(f"Power ON command {self.power_on_command} not found in available commands")
        
        # Execute all other commands by group
        for group, commands in self.command_groups.items():
            if group == 'power':
                # Skip power group as we handle power commands separately
                continue
            
            logger.info(f"Testing command group: {group}")
            
            # For menu group, execute menu command first
            if group == 'menu':
                menu_cmd = next((cmd for cmd, cfg in commands if cmd.lower() == 'menu'), None)
                if menu_cmd:
                    logger.info("Executing menu command first")
                    for cmd_name, cmd_config in commands:
                        if cmd_name == menu_cmd:
                            await self._execute_command(cmd_name, cmd_config)
                            break
            
            # Execute other commands in the group
            for cmd_name, cmd_config in commands:
                # Skip power ON/OFF commands and menu command if already executed
                if cmd_name == self.power_on_command or cmd_name == self.power_off_command:
                    continue
                if group == 'menu' and cmd_name.lower() == 'menu':
                    continue  # Skip if already executed
                
                await self._execute_command(cmd_name, cmd_config)
        
        # Execute power OFF command last
        if self.power_off_command:
            cmd_config = None
            for group, cmds in self.command_groups.items():
                for cmd_name, cfg in cmds:
                    if cmd_name == self.power_off_command:
                        cmd_config = cfg
                        break
                if cmd_config:
                    break
            
            if cmd_config:
                logger.info("Executing power OFF command")
                await self._execute_command(self.power_off_command, cmd_config)
            else:
                logger.warning(f"Power OFF command {self.power_off_command} not found in available commands")
    
    async def cleanup(self):
        """Clean up resources."""
        if self.device:
            await self.device.shutdown()
            logger.info(f"Device {self.device_id} shut down")
        
        if self.mqtt_client:
            await self.mqtt_client.disconnect()
            logger.info("Disconnected from MQTT broker")
    
    def print_results(self):
        """Print test results."""
        self.results.print_summary()


def setup_logging():
    """Configure logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Set lower log level for noisy libraries
    for logger_name in ["websockets.client", "aiohttp.client"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test device functionality.")
    parser.add_argument("--config", required=True, help="Path to device config file")
    parser.add_argument("--mode", required=True, choices=["rest", "mqtt", "both"], 
                        help="Interface to use for command execution")
    parser.add_argument("--wait", type=float, default=1.0, 
                        help="Time to wait between commands in seconds (default: 1.0)")
    parser.add_argument("--prompt", action="store_true", 
                        help="Prompt for parameter values (default: use defaults)")
    parser.add_argument("--include", type=str, 
                        help="Only include these commands (comma-separated)")
    parser.add_argument("--exclude", type=str, 
                        help="Exclude these commands (comma-separated)")
    
    args = parser.parse_args()
    
    # Convert include/exclude to sets if provided
    include_commands = None
    exclude_commands = None
    
    if args.include:
        include_commands = set(cmd.strip() for cmd in args.include.split(","))
    if args.exclude:
        exclude_commands = set(cmd.strip() for cmd in args.exclude.split(","))
    
    # Set up logging
    setup_logging()
    
    # Create and run the device tester
    tester = DeviceTester(
        config_path=args.config,
        mode=args.mode,
        wait_time=args.wait,
        prompt=args.prompt,
        include_commands=include_commands,
        exclude_commands=exclude_commands
    )
    
    try:
        await tester.setup()
        await tester.run_tests()
        tester.print_results()
    except Exception as e:
        logger.error(f"Error during test execution: {str(e)}", exc_info=True)
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 