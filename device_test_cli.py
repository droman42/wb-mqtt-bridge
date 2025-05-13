#!/usr/bin/env python3

import argparse
import asyncio
import logging
import json
import sys
from typing import Dict, Any, Optional, List, Tuple, cast

from app.device_manager import DeviceManager
from app.config_manager import ConfigManager
from app.schemas import BaseDeviceConfig, CommandParameterDefinition
from app.types import CommandResponse, StateT
from app.mqtt_client import MQTTClient

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("device_test_cli")

class DeviceTestCLI:
    """Command-line tool for testing devices."""
    
    def __init__(self):
        self.config_manager = None
        self.device_manager = None
        self.current_device = None
        self.device_id = None
        self.mqtt_client = None
    
    async def initialize(self, device_id: str) -> bool:
        """
        Initialize the configuration and device managers.
        
        Args:
            device_id: The ID of the device to initialize
            
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Initialize configuration manager
            logger.info(f"Initializing configuration manager...")
            self.config_manager = ConfigManager()
            # Config is loaded automatically in the constructor
            
            # Get system config to initialize MQTT client
            system_config = self.config_manager.get_system_config()
            
            # Initialize MQTT client first
            mqtt_broker_config = system_config.mqtt_broker
            logger.info(f"Initializing MQTT client with broker at {mqtt_broker_config.host}:{mqtt_broker_config.port}...")
            self.mqtt_client = MQTTClient({
                'host': mqtt_broker_config.host,
                'port': mqtt_broker_config.port,
                'client_id': mqtt_broker_config.client_id + "_cli",  # Add suffix to avoid ID conflicts
                'keepalive': mqtt_broker_config.keepalive,
                'auth': mqtt_broker_config.auth
            })
            
            # Improved MQTT connection handling
            connection_success = await self._connect_mqtt()
            
            # Initialize device manager with the configuration manager and MQTT client
            logger.info(f"Initializing device manager...")
            self.device_manager = DeviceManager(
                mqtt_client=self.mqtt_client,
                config_manager=self.config_manager
            )
            
            # Load device modules
            await self.device_manager.load_device_modules()
            
            # Get all device configurations
            device_configs = self.config_manager.get_all_device_configs()
            
            # Check if the device_id exists
            if device_id not in device_configs:
                logger.error(f"Device ID '{device_id}' not found in configuration")
                return False
            
            # Initialize only the specified device
            filtered_configs = {device_id: device_configs[device_id]}
            await self.device_manager.initialize_devices(filtered_configs)
            
            # Set MQTT client for the device
            for d_id, device in self.device_manager.devices.items():
                device.mqtt_client = self.mqtt_client
                logger.info(f"Device {d_id} initialized with MQTT client")
            
            # Only subscribe to topics if we have a working connection
            if connection_success:
                # Add device-specific subscriptions
                device_topics = {}
                for d_id, device in self.device_manager.devices.items():
                    topics = device.subscribe_topics()
                    if topics:
                        device_topics[d_id] = topics
                        logger.info(f"Device {d_id} will subscribe to topics: {topics}")
                
                # Set up subscriptions if needed
                if device_topics:
                    success = await self._setup_mqtt_subscriptions(device_topics)
                    if not success:
                        logger.warning("Failed to set up MQTT subscriptions. Device state updates may not work.")
            
            # Get the device instance
            self.current_device = self.device_manager.get_device(device_id)
            if not self.current_device:
                logger.error(f"Failed to initialize device '{device_id}'")
                return False
            
            # Final connection validation to ensure everything is ready
            await self._validate_mqtt_connection()
            
            self.device_id = device_id
            logger.info(f"Successfully initialized device '{device_id}'")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing device test CLI: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _connect_mqtt(self) -> bool:
        """
        Establish MQTT connection with proper validation.
        
        Returns:
            bool: True if connection was successful
        """
        logger.info("Establishing MQTT connection...")
        
        # First start the connection process
        connect_success = await self.mqtt_client.connect()
        if not connect_success:
            logger.error("Failed to start MQTT connection process")
            return False
            
        # Wait for connection to establish
        max_attempts = 5
        for attempt in range(max_attempts):
            if self.mqtt_client.connected:
                logger.info(f"MQTT connection established successfully on attempt {attempt+1}")
                return True
                
            logger.info(f"Waiting for MQTT connection to establish (attempt {attempt+1}/{max_attempts})...")
            await asyncio.sleep(1)  # Wait a second between checks
            
        logger.error("Failed to establish MQTT connection after multiple attempts")
        return False
        
    async def _setup_mqtt_subscriptions(self, device_topics: Dict[str, List[str]]) -> bool:
        """
        Set up MQTT subscriptions for devices.
        
        Args:
            device_topics: Dictionary mapping device IDs to topic lists
            
        Returns:
            bool: True if subscriptions were set up successfully
        """
        if not self.mqtt_client.connected:
            logger.error("Cannot set up subscriptions: MQTT client not connected")
            return False
            
        try:
            # Create topic handlers mapping
            topic_handlers = {
                topic: self.device_manager.get_message_handler(d_id) 
                for d_id, topics in device_topics.items()
                for topic in topics
            }
            
            if not topic_handlers:
                logger.info("No topics to subscribe to")
                return True
                
            logger.info(f"Setting up {len(topic_handlers)} topic subscriptions...")
            
            # Disconnect and reconnect with subscriptions
            await self.mqtt_client.disconnect()
            await asyncio.sleep(0.5)  # Brief pause before reconnecting
            
            sub_success = await self.mqtt_client.connect_and_subscribe(topic_handlers)
            if not sub_success:
                logger.error("Failed to set up MQTT subscriptions")
                return False
                
            # Give time for subscriptions to take effect
            await asyncio.sleep(1)
            
            logger.info("MQTT subscriptions set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up MQTT subscriptions: {str(e)}")
            return False
            
    async def _validate_mqtt_connection(self) -> None:
        """Validate MQTT connection and provide informative messages."""
        if not self.mqtt_client:
            logger.warning("MQTT client not initialized")
            return
            
        if not self.mqtt_client.connected:
            logger.warning("MQTT connection is not established - IR commands and state updates will fail")
            return
            
        # Test connection with a simple operation if possible
        try:
            # Try to publish to a test topic to validate connection
            test_topic = "/device_test_cli/connection_test"
            publish_success = await self.mqtt_client.publish(test_topic, "test")
            
            if publish_success:
                logger.info("MQTT connection validated with successful test publish")
            else:
                logger.warning("MQTT connection test failed - commands may not work properly")
                
        except Exception as e:
            logger.error(f"Error validating MQTT connection: {str(e)}")
    
    async def shutdown(self) -> bool:
        """
        Shutdown all initialized devices.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        try:
            # First disconnect MQTT client if it exists
            if hasattr(self, 'mqtt_client') and self.mqtt_client:
                logger.info(f"Disconnecting MQTT client...")
                await self.mqtt_client.disconnect()
            
            if self.device_manager:
                logger.info(f"Shutting down devices...")
                await self.device_manager.shutdown_devices()
            return True
        except Exception as e:
            logger.error(f"Error shutting down devices: {str(e)}")
            return False
    
    async def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute a command on the initialized device.
        
        Args:
            command: The command to execute
            params: Optional parameters for the command
            
        Returns:
            bool: True if the command was executed successfully, False otherwise
        """
        if not self.current_device:
            logger.error("No device initialized")
            return False
        
        try:
            logger.info(f"Executing command '{command}' on device '{self.device_id}'")
            response = await self.current_device.execute_action(command, params)
            
            # Print basic command result
            print("\n" + "="*50)
            print(f"COMMAND EXECUTION RESULT: {command}")
            print(f"Status: {'SUCCESS' if response.get('success', False) else 'FAILED'}")
            
            # Print error if any
            error = response.get('error')
            if error:
                print(f"Error: {error}")
                logger.error(f"Error: {error}")
            
            # Safely print result components with improved debugging
            print("\nRESULT DETAILS:")
            
            # Debug - print raw response structure first (to see what we're working with)
            print(f"Raw response keys: {list(response.keys())}")
            
            # First check for data directly in the response (top level by design)
            if 'data' in response:
                data_list = response['data']
                if isinstance(data_list, list):
                    print(f"Found {len(data_list)} items:")
                    for i, item in enumerate(data_list):
                        if isinstance(item, dict):
                            # Format dictionary items nicely
                            item_desc = []
                            for k, v in item.items():
                                item_desc.append(f"{k}={v}")
                            print(f"  {i+1}. {' | '.join(item_desc)}")
                        else:
                            print(f"  {i+1}. {item}")
                elif data_list:
                    print(f"Data: {data_list}")
            
            # For backward compatibility, still check result (though per design, data is always top-level)
            elif 'result' in response:
                result = response['result']
                if isinstance(result, dict):
                    print(f"Result contains keys: {list(result.keys())}")
                
                    # Handle result structure
                    if isinstance(result, dict):
                        # Print message if available
                        if 'message' in result:
                            print(f"Message: {result['message']}")
                        
                        # Check for data field in result (legacy format)
                        if 'data' in result:
                            data_list = result['data']
                            if isinstance(data_list, list):
                                print(f"Found {len(data_list)} items:")
                                for i, item in enumerate(data_list):
                                    if isinstance(item, dict):
                                        # Format dictionary items nicely
                                        item_desc = []
                                        for k, v in item.items():
                                            item_desc.append(f"{k}={v}")
                                        print(f"  {i+1}. {' | '.join(item_desc)}")
                                    else:
                                        print(f"  {i+1}. {item}")
                            elif data_list:
                                print(f"Data: {data_list}")
                
                    # If not a dict with expected fields, print the raw result
                    elif result is not None:
                        print(f"Raw result: {result}")
            
            # Print current device state
            state = self.current_device.get_current_state()
            print("\n" + "="*50)
            print("CURRENT DEVICE STATE:")
            
            # Convert state to dictionary
            state_dict = {}
            if hasattr(state, 'model_dump'):
                state_dict = state.model_dump()
            elif hasattr(state, 'dict'):
                state_dict = state.dict()
            else:
                # Fallback - try to access attributes directly
                for attr_name in dir(state):
                    # Skip private attributes and methods
                    if not attr_name.startswith('_') and not callable(getattr(state, attr_name)):
                        state_dict[attr_name] = getattr(state, attr_name)
            
            # Print state
            for key, value in state_dict.items():
                print(f"  {key}: {value}")
            
            print("="*50 + "\n")
            
            # Log completion
            logger.info(f"Command completed: {command}")
            
            return response.get('success', False)
            
        except Exception as e:
            logger.error(f"Error executing command '{command}': {str(e)}")
            print(f"\nError executing command '{command}': {str(e)}")
            return False
    
    def get_available_commands(self) -> List[Tuple[str, List[CommandParameterDefinition]]]:
        """
        Get a list of available commands for the initialized device.
        
        Returns:
            List of tuples containing command name and its parameter definitions
        """
        if not self.current_device:
            return []
        
        commands = []
        for cmd_name, cmd_config in self.current_device.get_available_commands().items():
            commands.append((cmd_name, cmd_config.params or []))
        
        return commands
    
    async def prompt_for_params(self, command: str, param_defs: List[CommandParameterDefinition]) -> Dict[str, Any]:
        """
        Prompt the user for parameter values based on parameter definitions.
        
        Args:
            command: The command being executed
            param_defs: List of parameter definitions
            
        Returns:
            Dict of parameter names to values
        """
        if not param_defs:
            return {}
        
        params = {}
        print(f"\nEnter parameters for command '{command}':")
        
        for param in param_defs:
            # Display parameter info
            required_str = "required" if param.required else "optional"
            default_str = f" (default: {param.default})" if param.default is not None else ""
            range_str = ""
            if param.min is not None and param.max is not None:
                range_str = f" (range: {param.min}-{param.max})"
            
            # Prompt for input
            prompt = f"  {param.name} ({param.type}, {required_str}){default_str}{range_str}: "
            value = input(prompt)
            
            # Skip if not required and no input provided
            if not value and not param.required:
                continue
            
            # Use default if not required and no input provided
            if not value and param.default is not None:
                value = param.default
            
            # Convert value to appropriate type
            try:
                if param.type == 'integer':
                    value = int(value)
                elif param.type == 'float':
                    value = float(value)
                elif param.type == 'boolean':
                    value = value.lower() in ('true', 'yes', 'y', '1')
                
                # Validate range if applicable
                if param.type in ('integer', 'float'):
                    if param.min is not None and param.max is not None:
                        typed_value = float(value)  # Ensure we can compare numerically
                        if typed_value < param.min or typed_value > param.max:
                            print(f"Error: Value must be between {param.min} and {param.max}")
                            # Re-prompt for this parameter
                            continue
                
                params[param.name] = value
                
            except ValueError:
                print(f"Error: Invalid value for {param.type} parameter")
                # Re-prompt for this parameter
                continue
        
        return params

async def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Device Test CLI')
    parser.add_argument('device_id', help='ID of the device to test')
    parser.add_argument('command', nargs='?', help='Command to execute (optional)')
    args = parser.parse_args()
    
    # Initialize CLI
    cli = DeviceTestCLI()
    try:
        # Initialize the device
        if not await cli.initialize(args.device_id):
            return 1
        
        if args.command:
            # Execute a single command and exit
            commands = cli.get_available_commands()
            for cmd_name, param_defs in commands:
                if cmd_name == args.command:
                    params = await cli.prompt_for_params(args.command, param_defs)
                    success = await cli.execute_command(args.command, params)
                    await cli.shutdown()
                    return 0 if success else 1
            
            logger.error(f"Command '{args.command}' not found")
            return 1
        else:
            # Interactive mode
            commands = cli.get_available_commands()
            
            while True:
                # Display available commands
                print("\nAvailable commands:")
                for i, (cmd_name, _) in enumerate(commands, 1):
                    print(f"  {i}. {cmd_name}")
                print("  q. Quit")
                
                # Get command selection
                selection = input("\nSelect a command (number or name): ")
                if selection.lower() in ('q', 'quit', 'exit'):
                    break
                
                # Find the selected command
                selected_command = None
                selected_params = None
                
                # Try to match by number
                try:
                    idx = int(selection) - 1
                    if 0 <= idx < len(commands):
                        selected_command, selected_params = commands[idx]
                except ValueError:
                    pass
                
                # Try to match by name
                if not selected_command:
                    for cmd_name, param_defs in commands:
                        if cmd_name == selection:
                            selected_command = cmd_name
                            selected_params = param_defs
                            break
                
                if selected_command:
                    # Prompt for parameters if needed
                    params = await cli.prompt_for_params(selected_command, selected_params)
                    
                    # Execute the command
                    await cli.execute_command(selected_command, params)
                else:
                    print("Invalid selection")
    
    finally:
        # Ensure we always shut down properly
        await cli.shutdown()

if __name__ == "__main__":
    asyncio.run(main()) 