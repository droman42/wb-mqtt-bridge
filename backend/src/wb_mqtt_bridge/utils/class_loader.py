"""
Dynamic class loading utilities for the device configuration system.

This module provides functions to dynamically load classes based on their names,
which enables the configuration system to instantiate the correct classes
based on the configuration files.
"""

import importlib
import inspect
import logging
from typing import Type, TypeVar, Optional, Dict, Any, Set

logger = logging.getLogger(__name__)

T = TypeVar('T')
class_cache: Dict[str, Any] = {}

def load_class_by_name(class_name: str, base_class: Type[T], module_prefix: str = "") -> Optional[Type[T]]:
    """
    Dynamically load a class by name, ensuring it's a subclass of the specified base class.
    
    Args:
        class_name: Name of the class to load
        base_class: Base class that the loaded class should inherit from
        module_prefix: Optional prefix for module paths (e.g., 'app.schemas.')
        
    Returns:
        The class if found and valid, None otherwise
    """
    # If the class name already includes a module, use it directly
    if '.' in class_name:
        module_path, class_name = class_name.rsplit('.', 1)
    else:
        # Otherwise, assume it's in one of our predefined modules
        # First try the direct module specified by the prefix (removing any trailing dot)
        direct_module = module_prefix.rstrip('.')
        
        possible_modules = []
        
        # Add the direct module if it's not empty
        if direct_module:
            possible_modules.append(direct_module)
            
        # Add standard module paths
        possible_modules.extend([
            f"{module_prefix}schemas",
            f"{module_prefix}devices",
        ])
        
        # Try each possible module
        for module_path in possible_modules:
            try:
                module = importlib.import_module(module_path)
                if hasattr(module, class_name):
                    cls = getattr(module, class_name)
                    if inspect.isclass(cls) and issubclass(cls, base_class):
                        return cls
            except (ImportError, AttributeError) as e:
                logger.debug(f"Could not load {class_name} from {module_path}: {str(e)}")
        
        logger.warning(f"Class {class_name} not found in any of the expected modules")
        return None
    
    # Try loading from the specified module
    try:
        module = importlib.import_module(module_path)
        if hasattr(module, class_name):
            cls = getattr(module, class_name)
            if inspect.isclass(cls) and issubclass(cls, base_class):
                return cls
            else:
                logger.warning(f"Found {class_name} in {module_path}, but it's not a subclass of {base_class.__name__}")
        else:
            logger.warning(f"Class {class_name} not found in module {module_path}")
    except ImportError as e:
        logger.warning(f"Could not import module {module_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Error loading class {class_name} from {module_path}: {str(e)}")
    
    return None

def validate_class_exists(class_name: str, base_class: Type[T], module_prefix: str = "") -> bool:
    """
    Validate that a class exists and is a subclass of the specified base class.
    
    Args:
        class_name: Name of the class to validate
        base_class: Base class that must be in the inheritance hierarchy
        module_prefix: Optional prefix for module name
        
    Returns:
        True if class exists and is valid, False otherwise
    """
    return load_class_by_name(class_name, base_class, module_prefix) is not None

def collect_validation_errors(class_names: Dict[str, str], base_class: Type[T], 
                             module_prefix: str = "") -> Set[str]:
    """
    Collect validation errors for multiple class names.
    
    Args:
        class_names: Dictionary mapping descriptive keys to class names
        base_class: Base class type to validate against
        module_prefix: Optional prefix for module name
        
    Returns:
        Set of error messages for invalid classes
    """
    errors = set()
    for key, class_name in class_names.items():
        if not validate_class_exists(class_name, base_class, module_prefix):
            errors.add(f"Invalid {key} class: {class_name}")
    return errors

def instantiate_from_config(config_data: Dict[str, Any], base_class: Type, module_prefix: str = "") -> Optional[Any]:
    """
    Instantiate an object from a configuration dictionary.
    
    Args:
        config_data: Configuration dictionary containing class information
        base_class: Base class that the instantiated class should inherit from
        module_prefix: Optional prefix for module paths
        
    Returns:
        An instance of the specified class if successful, None otherwise
    """
    config_class = config_data.get("config_class")
    if not config_class:
        logger.warning("No config_class specified in configuration data")
        return None
    
    cls = load_class_by_name(config_class, base_class, module_prefix)
    if not cls:
        return None
    
    try:
        # Use the create_from_dict classmethod if available
        if hasattr(cls, "create_from_dict") and callable(getattr(cls, "create_from_dict")):
            return cls.create_from_dict(config_data)
        
        # Fallback to direct instantiation
        return cls(**config_data)
    except Exception as e:
        logger.error(f"Error instantiating {config_class}: {str(e)}")
        return None 