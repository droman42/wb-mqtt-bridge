#!/usr/bin/env python
"""
Comprehensive test script for device configuration validation - Phase 5

This script tests the new device configuration architecture by:
1. Loading all configuration files
2. Testing device class and config class mapping
3. Validating command processing for each device type
4. Testing error handling
5. Generating a detailed report
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("config_test")

# Add parent directory to Python path to find app module
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
    from wb_mqtt_bridge.utils.validation import validate_device_configs
    from wb_mqtt_bridge.infrastructure.config.models import (
        BaseDeviceConfig,
        StandardCommandConfig,
        IRCommandConfig
    )
    from wb_mqtt_bridge.utils.class_loader import load_class_by_name
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running this script from the project root directory")
    sys.exit(1)

class ConfigTester:
    """Test harness for device configuration validation"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.devices_dir = os.path.join(config_dir, "devices")
        self.results = {
            "total_configs": 0,
            "valid_configs": 0,
            "invalid_configs": 0,
            "config_class_errors": 0,
            "device_class_errors": 0,
            "command_processing_errors": 0,
            "validation_errors": [],
            "device_results": {}
        }
        
        # Track expected config classes
        self.expected_config_classes = {
            "WirenboardIRDevice": "WirenboardIRDeviceConfig", 
            "RevoxA77ReelToReel": "RevoxA77ReelToReelConfig",
            "BroadlinkKitchenHood": "BroadlinkKitchenHoodConfig", 
            "LgTv": "LgTvDeviceConfig",
            "AppleTVDevice": "AppleTVDeviceConfig", 
            "EMotivaXMC2": "EmotivaXMC2DeviceConfig",
            "AuralicDevice": "AuralicDeviceConfig"
        }
        
    def load_and_validate_configs(self) -> bool:
        """Load and validate all device configurations in the devices directory"""
        logger.info(f"Testing device configurations in {self.devices_dir}")
        
        # First run the validation to check file structure and required fields
        valid_configs, errors = validate_device_configs(self.devices_dir)
        
        self.results["total_configs"] = len(valid_configs) + len(errors)
        self.results["valid_configs"] = len(valid_configs)
        self.results["invalid_configs"] = len(errors)
        
        if errors:
            for error in errors:
                logger.warning(f"Validation error: {error}")
                self.results["validation_errors"].append(str(error))
        
        # Process each valid configuration for detailed testing
        for device_id, config_data in valid_configs.items():
            self._test_device_config(device_id, config_data)
        
        return len(errors) == 0
    
    def _test_device_config(self, device_id: str, config_data: Dict[str, Any]) -> None:
        """Test an individual device configuration"""
        device_result = {
            "device_id": device_id,
            "device_name": config_data.get("device_name", "Unknown"),
            "device_class": config_data.get("device_class"),
            "config_class": config_data.get("config_class"),
            "command_count": len(config_data.get("commands", {})),
            "issues": []
        }
        
        # Test 1: Check device_class and config_class match
        device_class = config_data.get("device_class")
        config_class = config_data.get("config_class")
        
        if not device_class:
            device_result["issues"].append("Missing device_class field")
            self.results["device_class_errors"] += 1
        
        if not config_class:
            device_result["issues"].append("Missing config_class field")
            self.results["config_class_errors"] += 1
        
        # Test 2: Check expected mapping between device_class and config_class
        if device_class and config_class:
            expected_config_class = self.expected_config_classes.get(device_class)
            if expected_config_class and expected_config_class != config_class:
                device_result["issues"].append(
                    f"Mismatched config_class: expected '{expected_config_class}', got '{config_class}'"
                )
                self.results["config_class_errors"] += 1
        
        # Test 3: Test command processing
        if "commands" in config_data and config_class:
            try:
                # Get the config class
                cls = load_class_by_name(config_class, BaseDeviceConfig, "app.schemas.")
                if cls:
                    # Try to process commands
                    processed_commands = cls.process_commands(config_data.get("commands", {}))
                    device_result["processed_command_count"] = len(processed_commands)
                    
                    # Check if command types match expectations
                    self._validate_command_types(device_class, processed_commands, device_result)
                else:
                    device_result["issues"].append(f"Config class '{config_class}' not found")
                    self.results["config_class_errors"] += 1
            except Exception as e:
                device_result["issues"].append(f"Command processing error: {str(e)}")
                self.results["command_processing_errors"] += 1
        
        # Store the results for this device
        self.results["device_results"][device_id] = device_result
    
    def _validate_command_types(self, device_class: str, commands: Dict[str, Any], device_result: Dict[str, Any]) -> None:
        """Validate command types match expectations for device type"""
        expected_types = {
            "WirenboardIRDevice": IRCommandConfig,
            "RevoxA77ReelToReel": IRCommandConfig,
            "BroadlinkKitchenHood": StandardCommandConfig,
            # Others use standard commands or mixed types
        }
        
        expected_type = expected_types.get(device_class)
        if expected_type:
            for cmd_name, cmd in commands.items():
                if not isinstance(cmd, expected_type):
                    device_result["issues"].append(
                        f"Command '{cmd_name}' has unexpected type {type(cmd).__name__}, expected {expected_type.__name__}"
                    )
                    self.results["command_processing_errors"] += 1
    
    def test_config_manager(self) -> bool:
        """Test the ConfigManager with the new configuration files"""
        logger.info("Testing ConfigManager with device configurations")
        
        try:
            # Initialize ConfigManager
            config_manager = ConfigManager(self.config_dir)
            
            # Get all typed configs
            typed_configs = config_manager.get_all_typed_configs()
            
            # Record results
            self.results["config_manager"] = {
                "loaded_configs": len(typed_configs),
                "error": None
            }
            
            # Test reloading
            reload_success = config_manager.reload_configs()
            self.results["config_manager"]["reload_success"] = reload_success
            
            logger.info(f"ConfigManager loaded {len(typed_configs)} typed configurations")
            return True
        except Exception as e:
            logger.error(f"ConfigManager test failed: {str(e)}")
            self.results["config_manager"] = {
                "loaded_configs": 0,
                "error": str(e)
            }
            return False
    
    def generate_report(self) -> None:
        """Generate a detailed report of the test results"""
        print("\n" + "="*80)
        print(" DEVICE CONFIGURATION TEST REPORT ")
        print("="*80)
        
        print(f"\nTotal configurations tested: {self.results['total_configs']}")
        print(f"Valid configurations: {self.results['valid_configs']}")
        print(f"Invalid configurations: {self.results['invalid_configs']}")
        
        if self.results["validation_errors"]:
            print("\nValidation Errors:")
            for i, error in enumerate(self.results["validation_errors"], 1):
                print(f"  {i}. {error}")
        
        # Device class and config class errors
        print(f"\nDevice class errors: {self.results['device_class_errors']}")
        print(f"Config class errors: {self.results['config_class_errors']}")
        print(f"Command processing errors: {self.results['command_processing_errors']}")
        
        # ConfigManager results
        if "config_manager" in self.results:
            cm_results = self.results["config_manager"]
            print("\nConfigManager Test:")
            print(f"  Loaded configurations: {cm_results.get('loaded_configs', 0)}")
            if cm_results.get("error"):
                print(f"  Error: {cm_results['error']}")
            else:
                print(f"  Reload success: {cm_results.get('reload_success', False)}")
        
        # Print detailed device results
        print("\nDetailed Device Results:")
        for device_id, result in self.results["device_results"].items():
            print(f"\n  Device: {result['device_name']} ({device_id})")
            print(f"    Device Class: {result.get('device_class', 'N/A')}")
            print(f"    Config Class: {result.get('config_class', 'N/A')}")
            print(f"    Commands: {result.get('command_count', 0)}")
            
            if result.get("issues"):
                print("    Issues:")
                for issue in result["issues"]:
                    print(f"      - {issue}")
            else:
                print("    Status: OK")
        
        # Print summary
        print("\n" + "="*80)
        summary = "All configurations are valid" if (
            self.results["invalid_configs"] == 0 and
            self.results["device_class_errors"] == 0 and
            self.results["config_class_errors"] == 0 and
            self.results["command_processing_errors"] == 0
        ) else "Some configurations have issues"
        print(f" SUMMARY: {summary}")
        print("="*80 + "\n")
    
    def run_tests(self) -> bool:
        """Run all tests and generate a report"""
        validation_success = self.load_and_validate_configs()
        manager_success = self.test_config_manager()
        self.generate_report()
        return validation_success and manager_success

if __name__ == "__main__":
    tester = ConfigTester()
    success = tester.run_tests()
    sys.exit(0 if success else 1) 