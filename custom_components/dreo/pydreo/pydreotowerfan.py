"""Dreo API for controling fans."""

import logging
from typing import TYPE_CHECKING, Dict

from .constant import (
    LOGGER_NAME,
    OSCILLATE_KEY,
    SHAKEHORIZONANGLE_KEY,
    SPEED_RANGE
)

from .dreoapiresponseparser import DreoApiKeys
from .pydreofanbase import PyDreoFanBase
from .models import DreoDeviceDetails

_LOGGER = logging.getLogger(LOGGER_NAME)

if TYPE_CHECKING:
    from pydreo import PyDreo


class PyDreoTowerFan(PyDreoFanBase):
    """Base class for Dreo Fan API Calls."""

    def __init__(self, device_definition: DreoDeviceDetails, details: Dict[str, list], dreo: "PyDreo"):
        """Initialize air devices."""
        super().__init__(device_definition, details, dreo)
        
        self._oscillate = None
        self._oscillating = None
        self._shakehorizonangle = None

    @property
    def oscillating(self) -> bool:
        """Returns `True` if either horizontal or vertical oscillation is on."""
        if self._oscillate is not None:
            return self._oscillate
        elif self._oscillating is not None:
            return self._oscillating
        return None

    @oscillating.setter
    def oscillating(self, value: bool) -> None:

        """Enable or disable oscillation"""
        _LOGGER.debug("PyDreoFan:oscillating.setter")

        if self._oscillate is not None:
            self._send_command(OSCILLATE_KEY, value)
        else:
            raise NotImplementedError("Attempting to set oscillating on a device that doesn't support.")

    @property
    def shakehorizonangle(self) -> int:
        """Get the current oscillation angle"""
        if self._shakehorizonangle is not None:
            return self._shakehorizonangle

    @shakehorizonangle.setter
    def shakehorizonangle(self, value: int) -> None:
        """Set the oscillation angle."""
        _LOGGER.debug("PyDreoFan:shakehorizonangle.setter")
        if self._shakehorizonangle is not None:
            self._send_command(SHAKEHORIZONANGLE_KEY, int(value))           

    def update_state(self, state: dict):
        """Process the state dictionary from the REST API."""
        _LOGGER.debug("PyDreoFan:update_state")
        super().update_state(state)

        self._oscillate = self.get_state_update_value(state, DreoApiKeys.OSCILLATE)

    def handle_server_update(self, message):
        """Process a websocket update"""
        _LOGGER.debug("PyDreoFan:handle_server_update")
        super().handle_server_update(message)

        # Some tower fans use SHAKEHORIZON and some seem to use OSCON
        val_shakehorizon = self.get_server_update_key_value(message, OSCILLATE_KEY)
        if isinstance(val_shakehorizon, bool):
            self._oscillate = val_shakehorizon