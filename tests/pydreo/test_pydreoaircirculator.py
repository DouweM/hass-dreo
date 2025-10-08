"""Tests for Dreo Fans"""
# pylint: disable=used-before-assignment
import logging
from unittest.mock import patch
import pytest

from custom_components.dreo.pydreo.dreoapiresponseparser import DreoApiKeys
from  .imports import * # pylint: disable=W0401,W0614
from .testbase import TestBase, PATCH_SEND_COMMAND

from custom_components.dreo.pydreo import PyDreoAirCirculator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TestPyDreoAirCirculator(TestBase):
    """Test PyDreoAirCirculator class."""

    def test_HAF004S(self): # pylint: disable=invalid-name
        """Load circulator fan and test sending commands."""
        self.get_devices_file_name = "get_devices_HAF004S.json"
        self.pydreo_manager.load_devices()

        assert len(self.pydreo_manager.devices) == 1

        fan : PyDreoAirCirculator = self.pydreo_manager.devices[0]

        assert fan.horizontal_angle_range == (-60, 60)
        assert fan.vertical_angle_range == (-30, 90)
        assert fan.speed_range == (1, 9)
        assert fan.preset_modes == ['Normal', 'Natural', 'Sleep', 'Auto', 'Turbo', 'Custom']
        assert fan.oscillating is True
        assert fan.vertically_oscillating is True
        assert fan.vertical_osc_angle_top_range == (-30, 90)
        assert fan.vertical_osc_angle_bottom_range == (-30, 90)
        assert fan.horizontally_oscillating is False
        assert fan.horizontal_osc_angle_left_range == (-60, 60)
        assert fan.horizontal_osc_angle_right_range == (-60, 60)

        with patch(PATCH_SEND_COMMAND) as mock_send_command:
            fan.is_on = True
            mock_send_command.assert_called_once_with(fan, {DreoApiKeys.POWER_SWITCH: True})

        with patch(PATCH_SEND_COMMAND) as mock_send_command:
            fan.preset_mode = 'Normal'
            mock_send_command.assert_called_once_with(fan, {DreoApiKeys.MODE: 'Normal'})

        with pytest.raises(ValueError):
            fan.preset_mode = 'not_a_mode'

        with patch(PATCH_SEND_COMMAND) as mock_send_command:
            fan.fan_speed = 3
            mock_send_command.assert_called_once_with(fan, {WINDLEVEL_KEY: 3})

        with pytest.raises(ValueError):
            fan.fan_speed = 10

    @pytest.mark.skip(reason="Test diabled for v2.x")
    def test_HAF001S(self): # pylint: disable=invalid-name
        """Test HAF001S fan."""
        self.get_devices_file_name = "get_devices_HAF001S.json"
        self.pydreo_manager.load_devices()

        assert len(self.pydreo_manager.devices) == 1

        fan : PyDreoAirCirculator = self.pydreo_manager.devices[0]

        assert fan.speed_range == (1, 4)
        assert fan.horizontally_oscillating is not None
        assert fan.horizontally_oscillating is False
        assert fan.oscillating is not None

    @pytest.mark.skip(reason="Test diabled for v2.x")
    def test_HPF008S(self): # pylint: disable=invalid-name
        """Test HAF001S fan."""
        self.get_devices_file_name = "get_devices_HPF008S.json"
        self.pydreo_manager.load_devices()

        assert len(self.pydreo_manager.devices) == 1

        fan : PyDreoAirCirculator = self.pydreo_manager.devices[0]

        assert fan.is_on is True
        assert fan.speed_range == (1, 9)
        assert fan.preset_modes == None
        assert fan.horizontally_oscillating is False
        assert fan.oscillating is False
        assert fan.vertical_angle_range == (-30, 90)
        assert fan.temperature == 74

        with patch(PATCH_SEND_COMMAND) as mock_send_command:
            fan.is_on = True
            mock_send_command.assert_called_once_with(fan, {FANON_KEY: True})

