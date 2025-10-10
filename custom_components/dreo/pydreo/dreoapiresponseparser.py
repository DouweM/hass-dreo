"""Dreo API Response Parser."""

import logging
from logging import config
from typing import Optional, Union
from enum import Enum, IntEnum, StrEnum
from .constant import LOGGER_NAME


_LOGGER = logging.getLogger(LOGGER_NAME)

API_TIMEOUT = 30

NUMERIC = Optional[Union[int, float, str]]

class DreoApiKeys(StrEnum):
    """Dreo API Keys."""

    SPEED_RANGE = "speed_range"
    SPEED = "speed"
    PRESET_MODES = "preset_modes"
    MODE = "mode"

    POWER_SWITCH = "power_switch"
    OSCILLATE = "oscillate"
    OSCILLATION_MODE = "oscmode"

class DreoOscillationModes(StrEnum):
    """Dreo Oscillation Modes."""
    FIXED = "fixed"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    BOTH = "both"

class DreoApiResponseParser:
    """Dreo API Response Parser."""
    
    @staticmethod
    def find_node(data: dict, target_key=None) -> dict | list | None:
        """
        Recursively searches for a key  nested dictionary or list.

        Args:
            data (dict | list): The nested structure to search.
            target_key (str): The key to search for (optional).
        """
        
        # If the data is a dictionary, iterate through its keys and values
        if isinstance(data, dict):
            for key, value in data.items():
                # Check if the key matches the target key
                if target_key and key == target_key:
                    return value

                # Recurse into nested structures
                if isinstance(value, (dict, list)):
                    result = DreoApiResponseParser.find_node(value, target_key)
                    if result is not None:
                        return result

        # If the data is a list, iterate through its elements
        elif isinstance(data, list):
            for index, item in enumerate(data):

                # Recurse into nested structures
                if isinstance(item, (dict, list)):
                    result = DreoApiResponseParser.find_node(item, target_key)
                    if result is not None:
                        return result

        return None


    @staticmethod
    def get_config_node(details: dict[str, list], name: DreoApiKeys) -> dict | list | None:
        """Get the config node from the details."""
        node = DreoApiResponseParser.find_node(details, target_key=name)
        return node

    @staticmethod
    def get_config_range(details: dict[str, list], name: DreoApiKeys) -> tuple[int, int] | None:
        """Get the config range from the details."""
        range_node = DreoApiResponseParser.get_config_node(details, name)
        if (range_node is not None and isinstance(range_node, list) and len(range_node) == 2):
            return (range_node[0], range_node[1])
        return None
    
    @staticmethod
    def get_config_list(details: dict[str, list], name: DreoApiKeys) -> list | None:
        """Get the config list from the details."""
        list_node = DreoApiResponseParser.get_config_node(details, name)
        if (list_node is not None and isinstance(list_node, list)):
            return list_node
        return None    