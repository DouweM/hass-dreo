"""Base class for all tests. Contains a mock for call_dreo_api() function and instantiated Dreo object."""
# pylint: disable=W0201
import logging
import os
from typing import Optional
from unittest.mock import patch
import pytest
from  .imports import * # pylint: disable=W0401,W0614
from . import defaults
from . import call_json

logger = logging.getLogger(__name__)

API_REPONSE_BASE_PATH = 'tests/pydreo/api_responses/'

PATCH_BASE_PATH = 'custom_components.dreo.pydreo'
PATCH_SEND_COMMAND = f'{PATCH_BASE_PATH}.PyDreo.send_command'
PATCH_GET_DEVICE_SETTING = f'{PATCH_BASE_PATH}.PyDreo.get_device_setting'
PATCH_DREO_CLIENT_LOGIN = 'pydreo.client.DreoClient.login'
PATCH_DREO_CLIENT_GET_DEVICES = 'pydreo.client.DreoClient.get_devices'
PATCH_DREO_CLIENT_GET_STATUS = 'pydreo.client.DreoClient.get_status'

Defaults = defaults.Defaults

class TestBase:
    """Base class for all tests.

    Contains instantiated PyDreo object and mocked
    API call for call_api() function."""

    @property
    def get_devices_file_name(self):
        """Get the file name for the devices file."""
        return self._get_devices_file_name

    @get_devices_file_name.setter
    def get_devices_file_name(self, value: str):
        """Set the file name for the devices file."""
        self._get_devices_file_name = value

    @pytest.fixture(autouse=True, scope='function')
    def setup(self, caplog):
        """Fixture to instantiate Dreo object, start logging and start Mock.

        Attributes
        ----------
        self.mock_login : Mock
        self.mock_get_auth_token : Mock
        self.mock_get_devices : Mock
        self.mock_get_status : Mock
        self.pydreo_manager : PyDreo
        self.caplog : LogCaptureFixture

        Yields
        ------
        Class instance with mocked DreoClient functions and Dreo object
        """
        self._get_devices_file_name = None
        self.caplog = caplog

        # Mock the pydreo-cloud SDK methods
        self.mock_login_patch = patch(PATCH_DREO_CLIENT_LOGIN)
        self.mock_get_devices_patch = patch(PATCH_DREO_CLIENT_GET_DEVICES)
        self.mock_get_status_patch = patch(PATCH_DREO_CLIENT_GET_STATUS)
        self.mock_get_setting_patch = patch(PATCH_GET_DEVICE_SETTING)

        self.mock_login = self.mock_login_patch.start()
        self.mock_get_devices = self.mock_get_devices_patch.start()
        self.mock_get_status = self.mock_get_status_patch.start()
        self.mock_get_setting = self.mock_get_setting_patch.start()

        # Configure mocks
        self.mock_login.return_value = {'access_token': f'{Defaults.token}:NA', 'endpoint': 'https://open-api-us.dreo-tech.com'}
        self.mock_get_devices.side_effect = self.get_devices_mock
        self.mock_get_status.side_effect = self.get_device_status_mock
        self.mock_get_setting.side_effect = self.get_device_setting_mock

        self.pydreo_manager = PyDreo('EMAIL', 'PASSWORD', redact=True) # pylint: disable=E0601
        self.pydreo_manager.enabled = True
        self.pydreo_manager.token = Defaults.token
        self.pydreo_manager.account_id = Defaults.account_id
        caplog.set_level(logging.DEBUG)
        yield
        self.mock_login_patch.stop()
        self.mock_get_devices_patch.stop()
        self.mock_get_status_patch.stop()
        self.mock_get_setting_patch.stop()


    def get_devices_mock(self):
        """Mock for DreoClient.get_devices()"""
        logger.debug('Mock get_devices called')
        response = call_json.get_response_from_file(self.get_devices_file_name)
        # Return the list directly (new API format)
        if response and isinstance(response, list):
            return response
        return []

    def get_device_status_mock(self, devicesn: str):
        """Mock for DreoClient.get_status()"""
        logger.debug("Mock get_status called for: %s", devicesn)
        file_name = f"get_device_state_{devicesn}.json"
        if os.path.exists(API_REPONSE_BASE_PATH + file_name):
            logger.debug("Device state loaded from file: %s", API_REPONSE_BASE_PATH + file_name)
            response = call_json.get_response_from_file(file_name)
            # Return the mixed data directly (new API format)
            # Return the list directly (new API format)
            if response and isinstance(response, dict):
                return response
            return []
        else:
            logger.debug("No file found: %s", API_REPONSE_BASE_PATH + file_name)
        return {}

    def get_device_setting_mock(self, device, setting: str):
        """Mock for PyDreo.get_device_setting()"""
        logger.debug("Mock get_device_setting called for: %s, setting: %s", device.serial_number, setting)
        file_name = f"get_device_setting_{device.serial_number}_{setting}.json"
        if os.path.exists(API_REPONSE_BASE_PATH + file_name):
            logger.debug("Device setting loaded from file: %s", API_REPONSE_BASE_PATH + file_name)
            response = call_json.get_response_from_file(file_name)
            # Extract dataValue from the response
            if response and 'data' in response and 'dataValue' in response['data']:
                value_str = response['data']['dataValue']
                # Try to convert to int if possible
                try:
                    return int(value_str)
                except ValueError:
                    return value_str
        else:
            logger.debug("No settings file found: %s", API_REPONSE_BASE_PATH + file_name)
        return None


