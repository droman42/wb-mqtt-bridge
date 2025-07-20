"""
Utility script to automatically wrap all device classes with the dictionary-to-model converter.
This allows tests to use dictionary configurations with code that expects Pydantic models.
"""

import os
import sys
import inspect
import importlib
from pathlib import Path
from typing import List

# Add the parent directory to path to allow importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from tests.test_helpers import wrap_device_init


def find_device_classes() -> List[type]:
    """Find all device classes using entry points (same method as the application)."""
    device_classes = []
    
    try:
        from importlib.metadata import entry_points
    except ImportError:
        from importlib_metadata import entry_points  # Python < 3.8
    
    try:
        eps = entry_points()
        if hasattr(eps, 'select'):  # Python 3.10+
            device_entries = eps.select(group='wb_mqtt_bridge.devices')
        else:  # Python 3.8-3.9
            device_entries = eps.get('wb_mqtt_bridge.devices', [])
        
        for entry_point in device_entries:
            try:
                device_class = entry_point.load()
                if (inspect.isclass(device_class) and 
                    issubclass(device_class, BaseDevice) and 
                    device_class != BaseDevice):
                    device_classes.append(device_class)
            except Exception as e:
                print(f"Error loading device class from entry point '{entry_point.name}': {e}")
                
    except Exception as e:
        print(f"Error loading device entry points: {e}")
    
    return device_classes


def import_and_wrap_devices():
    """Import all device classes and wrap them with the dictionary converter."""
    wrapped_class_names = []
    
    # Find all device classes using entry points
    device_classes = find_device_classes()
    
    for device_class in device_classes:
        try:
            # Wrap the class to handle dictionary configs
            wrap_device_init(device_class)
            wrapped_class_names.append(device_class.__name__)
        except Exception as e:
            print(f"Error wrapping {device_class.__name__}: {e}")
    
    return wrapped_class_names


if __name__ == "__main__":
    # Only run if this script is executed directly
    wrapped_classes = import_and_wrap_devices()
    print(f"Wrapped {len(wrapped_classes)} device classes:")
    for cls_name in wrapped_classes:
        print(f"  - {cls_name}") 