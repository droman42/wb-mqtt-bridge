"""
Utility functions for safe serialization of objects to JSON.

This module provides helper functions to safely serialize objects to JSON,
particularly for state persistence of device states.
"""

import json
import logging
from typing import Any, Dict, List, Tuple
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)

def is_json_serializable(value: Any) -> bool:
    """
    Check if a value is directly JSON serializable.
    
    Args:
        value: The value to check
        
    Returns:
        bool: True if the value is directly JSON serializable, False otherwise
    """
    try:
        json.dumps(value)
        return True
    except (TypeError, OverflowError):
        return False

def get_serializable_value(value: Any) -> Any:
    """
    Convert a value to a JSON serializable form if possible.
    
    Args:
        value: The value to convert
        
    Returns:
        Any: A JSON serializable representation of the value
        
    Raises:
        TypeError: If the value cannot be converted to a JSON serializable form
    """
    # Handle None and primitives
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
        
    # Handle Pydantic models
    if hasattr(value, 'model_dump'):
        return value.model_dump()
        
    if hasattr(value, 'dict'):
        return value.dict()
        
    # Handle special types
    if isinstance(value, datetime):
        return value.isoformat()
        
    if isinstance(value, Enum):
        return value.value
        
    # Handle collections
    if isinstance(value, (list, tuple)):
        return [get_serializable_value(item) for item in value]
        
    if isinstance(value, dict):
        return {k: get_serializable_value(v) for k, v in value.items()}
        
    # Test direct serialization
    if is_json_serializable(value):
        return value
    
    # If all else fails, convert to string
    logger.warning(f"Converting non-serializable object of type {type(value).__name__} to string")
    return str(value)

def safely_serialize(obj: Any) -> Dict[str, Any]:
    """
    Safely serialize any object to a JSON serializable dictionary.
    
    This function tries various approaches to serialize an object,
    falling back to string conversion when necessary.
    
    Args:
        obj: The object to serialize
        
    Returns:
        Dict[str, Any]: A JSON serializable dictionary
    """
    try:
        # Handle None
        if obj is None:
            return {}
            
        # Handle dictionaries
        if isinstance(obj, dict):
            return {k: get_serializable_value(v) for k, v in obj.items()}
            
        # Handle Pydantic models
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
            
        if hasattr(obj, 'dict'):
            return obj.dict()
            
        # Handle objects with __dict__
        if hasattr(obj, '__dict__'):
            return {k: get_serializable_value(v) for k, v in obj.__dict__.items()}
            
        # If all else fails, log warning and convert to string representation
        logger.warning(f"Could not serialize object of type {type(obj).__name__}, using string representation")
        return {"__string_representation__": str(obj)}
            
    except Exception as e:
        logger.error(f"Error serializing object of type {type(obj).__name__}: {str(e)}")
        return {"__error__": f"Serialization failed: {str(e)}"}

def find_non_serializable_fields(obj: Any) -> List[Tuple[str, Any]]:
    """
    Find fields in an object that are not directly JSON serializable.
    
    Args:
        obj: The object to check
        
    Returns:
        List[Tuple[str, Any]]: List of (field_path, value) tuples for non-serializable fields
    """
    problematic_fields = []
    
    def check_value(path: str, value: Any):
        if is_json_serializable(value):
            return
            
        # Handle collections - check their contents recursively
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                check_value(f"{path}[{i}]", item)
            return
            
        if isinstance(value, dict):
            for k, v in value.items():
                check_value(f"{path}.{k}", v)
            return
            
        # Handle specially serializable types we know about
        if hasattr(value, 'model_dump') or hasattr(value, 'dict') or isinstance(value, (datetime, Enum)):
            return
            
        # If we get here, we've found a problem
        problematic_fields.append((path, value))
    
    # Handle different object types for the root
    if isinstance(obj, dict):
        for key, value in obj.items():
            check_value(key, value)
    elif hasattr(obj, '__dict__'):
        for key, value in obj.__dict__.items():
            check_value(key, value)
    elif hasattr(obj, 'model_fields_set'):  # Pydantic v2
        for key in obj.model_fields_set:
            check_value(key, getattr(obj, key))
    elif hasattr(obj, '__fields__'):  # Pydantic v1
        for key in obj.__fields__:
            check_value(key, getattr(obj, key))
    
    return problematic_fields

def describe_serialization_issues(obj: Any) -> List[str]:
    """
    Generate descriptive messages about serialization issues in an object.
    
    Args:
        obj: The object to check
        
    Returns:
        List[str]: List of descriptive error messages
    """
    problematic_fields = find_non_serializable_fields(obj)
    
    if not problematic_fields:
        return []
        
    return [
        f"Field '{path}' with type '{type(value).__name__}' is not directly JSON serializable"
        for path, value in problematic_fields
    ] 