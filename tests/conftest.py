"""
Pytest configuration for all tests.
"""

import os
import sys
import pytest

# Add the parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.auto_wrap_devices import import_and_wrap_devices


def pytest_configure(config):
    """Configure pytest before any tests are run."""
    # Wrap all device classes to handle dictionary configs
    wrapped_classes = import_and_wrap_devices()
    print(f"Wrapped {len(wrapped_classes)} device classes for testing") 