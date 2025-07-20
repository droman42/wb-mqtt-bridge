#!/usr/bin/env python3
"""
Device Function Test Script

This script automates testing of device functions by executing commands via REST API or MQTT.
It communicates with the running service through HTTP API endpoints instead of directly
instantiating device classes.

Usage:
    python device_test.py --config <path> --service-url <url> --mode <rest|mqtt|both> [options]

Options:
    --config <path>           Path to device config file (e.g., config/devices/device1.json)
    --service-url <url>       URL of the service (e.g., http://localhost:8000)
    --mode <rest|mqtt|both>   Interface to use for command execution via API endpoints
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
from typing import Dict, Any, Optional, Tuple, Set
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import required modules
import httpx
from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
from wb_mqtt_bridge.presentation.api.schemas import DeviceAction, MQTTMessage
from pydantic import ValidationError

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
    """Class to test device functionality through HTTP API."""
    
    def __init__(self, config_path: str, service_url: str, mode: str, wait_time: float, prompt: bool,
                 include_commands: Optional[Set[str]] = None, exclude_commands: Optional[Set[str]] = None):
        self.config_path = config_path
        self.service_url = service_url
        self.mode = mode
        self.wait_time = wait_time
        self.prompt = prompt
        self.include_commands = include_commands
        self.exclude_commands = exclude_commands
        
        self.device_config = None
        self.device_id = None
        self.config_manager = ConfigManager()
        self.http_client = None
        
        self.command_groups = {}
        self.power_on_command = None
        self.power_off_command = None
        
        self.results = TestResults()
    
    async def setup(self):
        """Set up the test environment."""
        logger.info(f"Setting up test environment for config: {self.config_path}")
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(base_url=self.service_url)
        
        # Load device configuration
        with open(self.config_path, 'r') as f:
            self.device_config = json.load(f)
        
        # Extract device ID from filename if not in config
        if 'device_id' not in self.device_config:
            self.device_id = os.path.basename(self.config_path).split('.')[0]
            self.device_config['device_id'] = self.device_id
        else:
            self.device_id = self.device_config['device_id']
        
        # Verify device exists via API endpoint
        try:
            device_url = f"/devices/{self.device_id}"
            response = await self.http_client.get(device_url)
            if response.status_code == 200:
                logger.info(f"Verified device exists: {self.device_id}")
            else:
                logger.warning(f"Device {self.device_id} not found via API. Status code: {response.status_code}")
        except Exception as e:
            logger.warning(f"Error checking device existence: {e}")
            logger.warning(f"Will attempt to continue with tests for device {self.device_id}")
        
        # Verify device commands from config
        commands = self.device_config.get('commands', {})
        if not commands:
            logger.warning("No commands found in device configuration")
        
        # Organize commands into groups
        self._organize_commands()
        
        logger.info(f"Setup complete for device {self.device_id}")
    
    def _organize_commands(self):
        """Organize commands into groups and identify power commands."""
        commands = self.device_config.get('commands', {})
        
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
        
        for param_name, default_value in required_params.items():
            if self.prompt:
                # Get parameter type (use default value's type or string)
                param_type = type(default_value) if default_value is not None else str
                param_desc = f"{param_name} ({param_type.__name__})"
                
                if default_value is not None:
                    user_input = input(f"Enter value for {param_desc} [{default_value}]: ")
                    if not user_input:
                        param_values[param_name] = default_value
                    else:
                        # Try to convert to the right type
                        try:
                            if param_type is bool:
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
                            # Basic type conversion attempt
                            if user_input.lower() in ['true', 'yes', 'y', '1', 'false', 'no', 'n', '0']:
                                param_values[param_name] = user_input.lower() in ['true', 'yes', 'y', '1']
                            elif user_input.isdigit():
                                param_values[param_name] = int(user_input)
                            elif user_input.replace('.', '', 1).isdigit():
                                param_values[param_name] = float(user_input)
                            else:
                                param_values[param_name] = user_input
                        except ValueError:
                            logger.warning(f"Invalid input for {param_name}")
                            param_values[param_name] = user_input
            else:
                # Use default value if available
                if default_value is not None:
                    param_values[param_name] = default_value
        
        return param_values
    
    def _fix_state_fields(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Add missing required fields to state."""
        if not state:
            state = {}
        
        # Ensure device_id is present
        if 'device_id' not in state:
            state['device_id'] = self.device_id
            logger.info(f"Added missing device_id={self.device_id} to state")
        
        # Ensure device_name is present
        if 'device_name' not in state:
            # Try to get device name from device config
            device_name = ''
            
            if isinstance(self.device_config, dict):
                # First check direct name field
                device_name = self.device_config.get('name', '')
                
                # If not in the top level, check device_info section
                if not device_name and isinstance(self.device_config, dict) and 'device_info' in self.device_config:
                    device_info = self.device_config.get('device_info', {})
                    if isinstance(device_info, dict):
                        device_name = device_info.get('name', '')
            
            # Fallback to extracting name from device_id
            if not device_name:
                # Convert device_id like "living_room_tv" to "Living Room TV"
                try:
                    device_name = ' '.join(word.capitalize() for word in self.device_id.split('_'))
                    logger.info(f"Generated device name '{device_name}' from device_id")
                except Exception as e:
                    logger.warning(f"Error generating name from device_id: {e}")
                    device_name = self.device_id
                
            state['device_name'] = device_name
            logger.info(f"Added missing device_name={device_name} to state")
            
        return state
    
    async def _execute_command(self, command: str, command_config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Execute a command via HTTP API and return success status and error message."""
        action_name = command_config.get('action', command)
        params = command_config.get('params', {})
        
        logger.info(f"Executing command: {command} (action: {action_name})")
        
        # Get parameter values
        param_values = await self._get_parameter_values(action_name, params)
        
        # Execute command via appropriate interface
        start_time = time.time()
        success = False
        error = None
        state = None
        
        try:
            if self.mode == 'rest':
                # Call the REST API endpoint
                url = f"/devices/{self.device_id}/action"
                payload = {"action": action_name, "params": param_values}
                
                # Validate payload against DeviceAction schema
                try:
                    device_action = DeviceAction(**payload)
                    # Update payload with validated data
                    payload = device_action.model_dump()
                    logger.info(f"Validated DeviceAction schema: {payload}")
                except ValidationError as ve:
                    logger.error(f"DeviceAction schema validation failed: {ve}")
                    return False, f"Schema validation error: {ve}"
                
                # Log HTTP request details
                full_url = f"{self.service_url}{url}"
                logger.info(f"HTTP Request: POST {full_url}")
                logger.info("HTTP Headers: {'Content-Type': 'application/json'}")
                logger.info(f"HTTP Payload: {json.dumps(payload)}")
                
                response = await self.http_client.post(url, json=payload)
                
                # Parse the response and check for validation errors in response
                if response.status_code == 200:
                    response_data = response.json()
                    success = response_data.get("success", False)
                    if not success:
                        error = response_data.get("message", "Unknown REST error")
                    state = response_data.get("state")
                    
                    # Additional validation of the state data
                    if state and isinstance(state, dict):
                        if 'device_id' not in state or 'device_name' not in state:
                            # Try to fix the state by adding missing fields
                            state = self._fix_state_fields(state)
                else:
                    success = False
                    try:
                        # Try to extract detailed error message
                        error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                        error = error_data.get("detail", response.text)
                        
                        # Look for Pydantic validation errors in the response
                        if "validation error" in error.lower() or "validationerror" in error.lower():
                            logger.error(f"Server-side validation error detected: {error}")
                            if "device_id" in error and "device_name" in error:
                                logger.error("Missing required fields in device state: device_id and device_name")
                                
                        # Add status code for more context
                        error = f"HTTP {response.status_code}: {error}"
                    except ValueError:
                        # If JSON parsing fails
                        error = f"HTTP {response.status_code}: {response.text}"
            
            elif self.mode == 'mqtt':
                # Get MQTT topic from command config
                topic = command_config.get('topic')
                if not topic:
                    logger.warning(f"No MQTT topic found for command {command}")
                    return False, "No MQTT topic in config"
                
                # Call the MQTT publish endpoint
                mqtt_payload = {"action": action_name, "params": param_values}
                mqtt_payload_string = json.dumps(mqtt_payload)
                
                publish_url = "/publish"
                publish_data = {"topic": topic, "payload": mqtt_payload_string}
                
                # Validate MQTT message against MQTTMessage schema
                try:
                    mqtt_message = MQTTMessage(**publish_data)
                    # Update payload with validated data
                    publish_data = mqtt_message.model_dump()
                    logger.info(f"Validated MQTTMessage schema: {publish_data}")
                except ValidationError as ve:
                    logger.error(f"MQTTMessage schema validation failed: {ve}")
                    return False, f"Schema validation error: {ve}"
                
                # Log HTTP request details
                full_url = f"{self.service_url}{publish_url}"
                logger.info(f"HTTP Request: POST {full_url}")
                logger.info("HTTP Headers: {'Content-Type': 'application/json'}")
                logger.info(f"HTTP Payload: {json.dumps(publish_data)}")
                
                response = await self.http_client.post(publish_url, json=publish_data)
                
                if response.status_code == 200 and response.json().get("success", False):
                    # Wait for device state update
                    await asyncio.sleep(self.wait_time)
                    
                    # Poll device state to check if command was successful
                    status_url = f"/devices/{self.device_id}"
                    
                    # Log HTTP request details
                    full_url = f"{self.service_url}{status_url}"
                    logger.info(f"HTTP Request: GET {full_url}")
                    logger.info("HTTP Headers: {'Accept': 'application/json'}")
                    
                    status_response = await self.http_client.get(status_url)
                    
                    if status_response.status_code == 200:
                        state = status_response.json()
                        
                        # Check for required fields in state
                        if isinstance(state, dict):
                            if 'device_id' not in state or 'device_name' not in state:
                                # Try to fix the state by adding missing fields
                                state = self._fix_state_fields(state)
                        
                        # Try to infer success from state
                        last_action = state.get("last_action")
                        if last_action == action_name:
                            success = True
                        else:
                            # If we can't verify success via last_action, check for error fields
                            success = not state.get("error") and not state.get("last_error")
                            if not success:
                                error = state.get("error") or state.get("last_error") or "Device state did not update as expected after MQTT command."
                    else:
                        success = False
                        try:
                            # Try to extract detailed error message
                            error_data = status_response.json() if status_response.headers.get("content-type") == "application/json" else {}
                            error = f"Status poll failed: HTTP {status_response.status_code}: {error_data.get('detail', status_response.text)}"
                            
                            # Check for validation errors
                            if isinstance(error_data.get('detail'), str) and "validation error" in error_data.get('detail', '').lower():
                                logger.error(f"Server-side validation error detected in device state: {error_data.get('detail')}")
                                if "device_id" in error_data.get('detail', '') and "device_name" in error_data.get('detail', ''):
                                    logger.error("Missing required fields in device state: device_id and device_name")
                        except ValueError:
                            error = f"Status poll failed: HTTP {status_response.status_code}: {status_response.text}"
                else:
                    success = False
                    try:
                        # Try to extract detailed error message
                        error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                        error = f"/publish call failed: HTTP {response.status_code}: {error_data.get('detail', response.text)}"
                    except ValueError:
                        error = f"/publish call failed: HTTP {response.status_code}: {response.text}"
            
            else:  # mode == 'both'
                # First try REST
                url = f"/devices/{self.device_id}/action"
                payload = {"action": action_name, "params": param_values}
                
                # Validate payload against DeviceAction schema
                try:
                    device_action = DeviceAction(**payload)
                    # Update payload with validated data
                    payload = device_action.model_dump()
                    logger.info(f"Validated DeviceAction schema: {payload}")
                except ValidationError as ve:
                    logger.error(f"DeviceAction schema validation failed: {ve}")
                    return False, f"Schema validation error: {ve}"
                
                # Log HTTP request details
                full_url = f"{self.service_url}{url}"
                logger.info(f"HTTP Request: POST {full_url}")
                logger.info("HTTP Headers: {'Content-Type': 'application/json'}")
                logger.info(f"HTTP Payload: {json.dumps(payload)}")
                
                rest_response = await self.http_client.post(url, json=payload)
                
                rest_success = False
                rest_error = None
                
                if rest_response.status_code == 200:
                    response_data = rest_response.json()
                    rest_success = response_data.get("success", False)
                    if not rest_success:
                        rest_error = response_data.get("message", "Unknown REST error")
                    state = response_data.get("state")
                    
                    # Additional validation of the state data
                    if state and isinstance(state, dict):
                        if 'device_id' not in state or 'device_name' not in state:
                            # Try to fix the state by adding missing fields
                            state = self._fix_state_fields(state)
                else:
                    try:
                        # Try to extract detailed error message
                        error_data = rest_response.json() if rest_response.headers.get("content-type") == "application/json" else {}
                        rest_error = error_data.get("detail") if rest_response.headers.get("content-type") == "application/json" else rest_response.text
                        
                        # Look for Pydantic validation errors in the response
                        if isinstance(rest_error, str) and ("validation error" in rest_error.lower() or "validationerror" in rest_error.lower()):
                            logger.error(f"Server-side validation error detected: {rest_error}")
                            if "device_id" in rest_error and "device_name" in rest_error:
                                logger.error("Missing required fields in device state: device_id and device_name")
                                logger.error("This may be a configuration issue with the device state schema")
                    except ValueError:
                        rest_error = f"HTTP {rest_response.status_code}: {rest_response.text}"
                
                await asyncio.sleep(self.wait_time)
                
                # Then try MQTT
                mqtt_success = False
                mqtt_error = None
                
                topic = command_config.get('topic')
                if topic:
                    mqtt_payload = {"action": action_name, "params": param_values}
                    mqtt_payload_string = json.dumps(mqtt_payload)
                    
                    publish_url = "/publish"
                    publish_data = {"topic": topic, "payload": mqtt_payload_string}
                    
                    # Validate MQTT message against MQTTMessage schema
                    mqtt_validation_passed = True
                    try:
                        mqtt_message = MQTTMessage(**publish_data)
                        # Update payload with validated data
                        publish_data = mqtt_message.model_dump()
                        logger.info(f"Validated MQTTMessage schema: {publish_data}")
                    except ValidationError as ve:
                        mqtt_error = f"Schema validation error: {ve}"
                        logger.error(f"MQTTMessage schema validation failed: {ve}")
                        mqtt_success = False
                        mqtt_validation_passed = False
                    
                    # Only proceed with MQTT if validation passed
                    if mqtt_validation_passed:
                        # Log HTTP request details
                        full_url = f"{self.service_url}{publish_url}"
                        logger.info(f"HTTP Request: POST {full_url}")
                        logger.info("HTTP Headers: {'Content-Type': 'application/json'}")
                        logger.info(f"HTTP Payload: {json.dumps(publish_data)}")
                        
                        mqtt_response = await self.http_client.post(publish_url, json=publish_data)
                        
                        if mqtt_response.status_code == 200 and mqtt_response.json().get("success", False):
                            # Wait for state update
                            await asyncio.sleep(self.wait_time)
                            
                            # Poll device state
                            status_url = f"/devices/{self.device_id}"
                            
                            # Log HTTP request details
                            full_url = f"{self.service_url}{status_url}"
                            logger.info(f"HTTP Request: GET {full_url}")
                            logger.info("HTTP Headers: {'Accept': 'application/json'}")
                            
                            status_response = await self.http_client.get(status_url)
                            
                            if status_response.status_code == 200:
                                state = status_response.json()
                                
                                # Check for required fields in state
                                if isinstance(state, dict):
                                    if 'device_id' not in state or 'device_name' not in state:
                                        # Try to fix the state by adding missing fields
                                        state = self._fix_state_fields(state)
                                
                                # Infer success
                                last_action = state.get("last_action")
                                if last_action == action_name:
                                    mqtt_success = True
                                else:
                                    # If we can't verify success via last_action, check for error fields
                                    mqtt_success = not state.get("error") and not state.get("last_error")
                                    if not mqtt_success:
                                        mqtt_error = state.get("error") or state.get("last_error") or "Device state did not update as expected"
                            else:
                                mqtt_success = False
                                try:
                                    # Try to extract detailed error message
                                    error_data = status_response.json() if status_response.headers.get("content-type") == "application/json" else {}
                                    mqtt_error = f"Status poll failed: HTTP {status_response.status_code}: {error_data.get('detail', status_response.text)}"
                                    
                                    # Check for validation errors
                                    if isinstance(error_data.get('detail'), str) and "validation error" in error_data.get('detail', '').lower():
                                        logger.error(f"Server-side validation error detected in device state: {error_data.get('detail')}")
                                        if "device_id" in error_data.get('detail', '') and "device_name" in error_data.get('detail', ''):
                                            logger.error("Missing required fields in device state: device_id and device_name")
                                except ValueError:
                                    mqtt_error = f"Status poll failed: HTTP {status_response.status_code}: {status_response.text}"
                        else:
                            mqtt_success = False
                            try:
                                # Try to extract detailed error message
                                error_data = mqtt_response.json() if mqtt_response.headers.get("content-type") == "application/json" else {}
                                mqtt_error = f"/publish call failed: HTTP {mqtt_response.status_code}: {error_data.get('detail', mqtt_response.text)}"
                            except ValueError:
                                mqtt_error = f"/publish call failed: HTTP {mqtt_response.status_code}: {mqtt_response.text}"
                else:
                    mqtt_error = "No MQTT topic in config"
                
                # Combine results
                success = rest_success or mqtt_success
                if not success:
                    if rest_error and mqtt_error:
                        error = f"REST: {rest_error}; MQTT: {mqtt_error}"
                    else:
                        error = rest_error or mqtt_error
        
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
        if state:
            logger.info(f"Device state after command: {json.dumps(state, default=str)}")
        
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
        if self.http_client:
            await self.http_client.aclose()
            logger.info("Closed HTTP client connection")
    
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
    for logger_name in ["websockets.client", "aiohttp.client", "httpx"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test device functionality via HTTP API.")
    parser.add_argument("--config", required=True, help="Path to device config file")
    parser.add_argument("--service-url", required=True, help="URL of the service (e.g., http://localhost:8000)")
    parser.add_argument("--mode", choices=["rest", "mqtt", "both"], required=True,
                        help="Interface to use for command execution via API endpoints")
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
    logger.info(f"Starting test run for {args.config} in {args.mode} mode using service {args.service_url}")
    tester = DeviceTester(
        config_path=args.config,
        service_url=args.service_url,
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