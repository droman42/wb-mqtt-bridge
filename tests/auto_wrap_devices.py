"""
Utility script to automatically wrap all device classes with the dictionary-to-model converter.
This allows tests to use dictionary configurations with code that expects Pydantic models.
"""

import os
import sys
import inspect
import importlib
from pathlib import Path
from typing import List, Type

# Add the parent directory to path to allow importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from devices.base_device import BaseDevice
from tests.test_helpers import wrap_device_init


def find_device_modules() -> List[str]:
    """Find all Python modules in the devices directory."""
    devices_dir = Path(os.path.join(os.path.dirname(__file__), '..', 'devices'))
    return [
        f"devices.{f.stem}" for f in devices_dir.glob("*.py")
        if f.is_file() and not f.name.startswith('__')
    ]


def import_and_wrap_devices():
    """Import all device modules and wrap device classes with the dictionary converter."""
    device_classes = []
    
    # Find and import all device modules
    for module_name in find_device_modules():
        try:
            module = importlib.import_module(module_name)
            
            # Find all classes in the module that derive from BaseDevice
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and issubclass(obj, BaseDevice) and obj != BaseDevice):
                    # Wrap the class to handle dictionary configs
                    wrap_device_init(obj)
                    device_classes.append(obj.__name__)
                    
        except (ImportError, AttributeError) as e:
            print(f"Error importing {module_name}: {e}")
    
    return device_classes


if __name__ == "__main__":
    # Only run if this script is executed directly
    wrapped_classes = import_and_wrap_devices()
    print(f"Wrapped {len(wrapped_classes)} device classes:")
    for cls_name in wrapped_classes:
        print(f"  - {cls_name}") 