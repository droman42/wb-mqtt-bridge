"""
Validation module for device configurations.

This module provides functions to validate device configurations,
discover configuration files, and ensure they meet the required format.
"""

import logging
import os
from typing import Dict, Set, List, Optional, Tuple, Any, Type
import json
from pathlib import Path
import glob

from app.schemas import BaseDeviceConfig
from app.class_loader import validate_class_exists, collect_validation_errors

logger = logging.getLogger(__name__)

# Required fields for device configuration files
REQUIRED_FIELDS = ["device_id", "device_name", "device_class", "config_class"]

def validate_config_file_structure(file_path: str) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
    """
    Validate basic structure of a device configuration file.
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        Tuple containing:
        - Boolean indicating if validation passed
        - Dictionary containing the file data if successful, None otherwise
        - List of error messages
    """
    errors = []
    
    if not os.path.exists(file_path):
        errors.append(f"Configuration file does not exist: {file_path}")
        return False, None, errors
    
    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in configuration file {file_path}: {str(e)}")
        return False, None, errors
    
    # Check for required top-level fields
    missing_fields = [field for field in REQUIRED_FIELDS if field not in config_data]
    
    if missing_fields:
        errors.append(f"Missing required fields in {file_path}: {', '.join(missing_fields)}")
        return False, None, errors
    
    # Check that device_id matches filename pattern (optional)
    device_id = config_data.get('device_id')
    filename = os.path.basename(file_path)
    if device_id and filename != f"{device_id}.json" and not filename.startswith(f"{device_id}_"):
        # This is just a warning, not an error
        logger.warning(
            f"Device ID '{device_id}' does not match filename pattern '{filename}'. "
            f"Consider renaming to '{device_id}.json' for consistency."
        )
    
    return len(errors) == 0, config_data, errors

def validate_class_references(config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate that device_class and config_class references exist.
    
    Args:
        config_data: Device configuration data
        
    Returns:
        Tuple containing:
        - Boolean indicating if validation passed
        - List of error messages
    """
    errors = []
    
    # Collect classes to validate
    classes_to_validate = {
        "device implementation": config_data.get('device_class', ''),
        "configuration": config_data.get('config_class', '')
    }
    
    # Validate device_class against BaseDevice
    device_class = classes_to_validate["device implementation"]
    if device_class and not validate_class_exists(device_class, object, "devices."):
        errors.append(f"Device class '{device_class}' not found")
    
    # Validate config_class against BaseDeviceConfig
    config_class = classes_to_validate["configuration"]
    if config_class and not validate_class_exists(config_class, BaseDeviceConfig, "app.schemas."):
        errors.append(f"Configuration class '{config_class}' not found")
    
    return len(errors) == 0, errors

def discover_config_files(config_dir: str) -> List[str]:
    """
    Discover all JSON configuration files in the specified directory.
    
    Args:
        config_dir: Path to the directory containing configuration files
        
    Returns:
        List of paths to discovered JSON files
    """
    config_files = []
    
    # Check if directory exists
    if not os.path.isdir(config_dir):
        logger.error(f"Configuration directory not found: {config_dir}")
        return config_files
    
    # Find all JSON files
    pattern = os.path.join(config_dir, "*.json")
    config_files = glob.glob(pattern)
    
    logger.info(f"Discovered {len(config_files)} configuration files in {config_dir}")
    return config_files

def load_config_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Load and parse a JSON configuration file.
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        The parsed configuration as a dictionary, or None if loading failed
    """
    try:
        with open(file_path, 'r') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error loading {file_path}: {str(e)}")
    
    return None

def validate_config_file(file_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate a single configuration file.
    
    Args:
        file_path: Path to the configuration file
        
    Returns:
        Tuple of (config_data, error_message). If validation succeeds, error_message is None.
        If validation fails, config_data may be None and error_message contains the error.
    """
    # Load the file
    config = load_config_file(file_path)
    if not config:
        return None, f"Failed to load configuration file: {file_path}"
    
    # Check required fields
    missing_fields = [field for field in REQUIRED_FIELDS if field not in config]
    if missing_fields:
        return config, f"Missing required fields in {file_path}: {', '.join(missing_fields)}"
    
    # Check device_id matches filename (now just a warning, not an error)
    expected_filename = f"{config['device_id']}.json"
    actual_filename = os.path.basename(file_path)
    if expected_filename != actual_filename:
        logger.warning(
            f"Device ID '{config['device_id']}' does not match filename '{actual_filename}'. "
            f"For better organization, consider renaming to '{expected_filename}'."
        )
    
    return config, None

def validate_device_configs(config_dir: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Validate all device configuration files in the specified directory.
    
    Args:
        config_dir: Path to the directory containing configuration files
        
    Returns:
        Tuple of (valid_configs, errors) where valid_configs is a dictionary mapping
        device_id to configuration data, and errors is a list of error messages.
    """
    valid_configs = {}
    errors = []
    
    # Discover all configuration files
    config_files = discover_config_files(config_dir)
    
    # Track device IDs to check for duplicates
    device_ids = set()
    
    # Validate each file
    for file_path in config_files:
        config, error = validate_config_file(file_path)
        
        # Handle validation errors
        if error:
            errors.append(error)
            continue
            
        # Skip if config is None (though validate_config_file should not return None without an error)
        if config is None:
            errors.append(f"Unknown error processing {file_path}")
            continue
        
        # Check for duplicate device IDs
        device_id = config["device_id"]
        if device_id in device_ids:
            errors.append(f"Duplicate device ID '{device_id}' in {file_path}")
            continue
        
        # Add to valid configs
        device_ids.add(device_id)
        valid_configs[device_id] = config
    
    logger.info(f"Validated {len(valid_configs)} valid configurations with {len(errors)} errors")
    return valid_configs, errors 