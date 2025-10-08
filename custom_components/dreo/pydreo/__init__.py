"""Dreo API Library."""

# flake8: noqa
# from .pydreo import PyDreo
import logging
import threading
import sys
import hashlib

import json
from itertools import chain
from typing import Optional, Tuple
from asyncio.exceptions import CancelledError

from pydreo.client import DreoClient 

from .constant import *
from .helpers import Helpers
from .models import *
from .commandtransport import CommandTransport
from .pydreobasedevice import PyDreoBaseDevice, UnknownModelError, UnknownProductError
from .pydreounknowndevice import PyDreoUnknownDevice
from .pydreotowerfan import PyDreoTowerFan
from .pydreoaircirculator import PyDreoAirCirculator
from .pydreoceilingfan import PyDreoCeilingFan
from .pydreoairpurifier import PyDreoAirPurifier
from .pydreoheater import PyDreoHeater
from .pydreoairconditioner import PyDreoAC
from .pydreochefmaker import PyDreoChefMaker
from .pydreohumidifier import PyDreoHumidifier
from .pydreodehumidifier import PyDreoDehumidifier
from .pydreoevaporativecooler import PyDreoEvaporativeCooler

_LOGGER = logging.getLogger(LOGGER_NAME)

_DREO_DEVICE_TYPE_TO_CLASS = {
    DreoDeviceType.TOWER_FAN: PyDreoTowerFan,
    DreoDeviceType.AIR_CIRCULATOR: PyDreoAirCirculator,
    DreoDeviceType.AIR_PURIFIER: PyDreoAirPurifier,
    DreoDeviceType.CEILING_FAN: PyDreoCeilingFan,
    DreoDeviceType.HEATER: PyDreoHeater,
    DreoDeviceType.AIR_CONDITIONER: PyDreoAC,
    DreoDeviceType.CHEF_MAKER: PyDreoChefMaker,
    DreoDeviceType.HUMIDIFIER: PyDreoHumidifier,
    DreoDeviceType.DEHUMIDIFIER: PyDreoDehumidifier,
    DreoDeviceType.EVAPORATIVE_COOLER: PyDreoEvaporativeCooler
}

class PyDreo:  # pylint: disable=function-redefined
    """Dreo API functions."""

    def __init__(self,
                 username,
                 password,
                 redact=True,
                 debug_test_mode=False,
                 debug_test_mode_payload=None) -> None:
        self._transport = CommandTransport(self._transport_consume_message)

        """Initialize Dreo class with username, password and time zone."""
        self.auth_region = DREO_AUTH_REGION_NA  # Will get the region from the auth call

        self._redact = redact
        if redact:
            self.redact = redact
        self.raw_response = None
        self.username : str = username
        self.password : str  = password
        self.token = None
        self.account_id = None
        self.devices = None
        self.enabled = False
        self.in_process = False
        self._dev_list = {}
        self._device_list_by_sn = {}
        self.devices: list[PyDreoBaseDevice] = []

        self.debug_test_mode : bool = debug_test_mode
        self.debug_test_mode_payload : dict = debug_test_mode_payload

        # Initialize the new pydreo-cloud client
        self._cloud_client : DreoClient = None
        if not debug_test_mode:
           # MD5 hash the password for the new API
            hashed_password = hashlib.md5(password.encode()).hexdigest()
            self._cloud_client = DreoClient(username=username, password=hashed_password)
            _LOGGER.info("Using pydreo-cloud SDK")

        if self.debug_test_mode:
            _LOGGER.error("Debug Test Mode is enabled!")
            if self.debug_test_mode_payload is None:
                _LOGGER.error("Debug Test Mode payload is None!")

    @property
    def api_server_region(self) -> str:
        """Return region."""
        if self.auth_region == DREO_AUTH_REGION_NA:
            return DREO_API_REGION_US
        elif self.auth_region == DREO_AUTH_REGION_EU:
            return DREO_API_REGION_EU
        else:
            _LOGGER.error("Invalid Auth Region: %s", self.auth_region)

    @property
    def auto_reconnect(self) -> bool:
        """Return auto_reconnect option."""
        return self._transport.auto_reconnect

    @auto_reconnect.setter
    def auto_reconnect(self, value: bool) -> None:
        """Set auto_reconnect option."""
        _LOGGER.debug("Setting auto_reconnect to %s", value)
        self._transport.auto_reconnect = value

    @property
    def redact(self) -> bool:
        """Return debug flag."""
        return self._redact

    @redact.setter
    def redact(self, new_flag: bool) -> None:
        """Set debug flag."""
        if new_flag:
            Helpers.shouldredact = True
        elif new_flag is False:
            Helpers.shouldredact = False
        self._redact = new_flag

    @staticmethod
    def set_dev_id(devices: list) -> list:
        """Correct devices without cid or uuid."""
        dev_num = 0
        dev_rem = []
        for dev in devices:
            if dev.get(DEVICESN_KEY) is not None:
                dev[DEVICESN_KEY] = dev[DEVICESN_KEY]
            dev_num += 1
            if dev_rem:
                devices = [i for j, i in enumerate(devices) if j not in dev_rem]
        return devices

    def _process_devices(self, dev_list: list) -> bool:
        """Instantiate Device Objects."""
        devices = self.set_dev_id(dev_list)
        _LOGGER.debug("pydreo._process_devices")
        num_devices = 0
        for _, v in self._dev_list.items():
            if isinstance(v, list):
                num_devices += len(v)
            else:
                num_devices += 1

        if not devices:
            _LOGGER.warning("No devices found in api return")
            return False
        if num_devices == 0:
            _LOGGER.debug("New device list initialized")

        for dev in devices:
            # Get the state of the device...separate API call...boo
            try:
                model = dev.get("model", None)
                
                _LOGGER.debug("Found device with model %s", model)

                if model is not None: 
                    # Get the prefix of the model number to match against the supported devices.
                    # Not all models will have known prefixes.
                    model_prefix = None
                    for prefix in SUPPORTED_MODEL_PREFIXES:
                        if model[:len(prefix):] == prefix:
                            model_prefix = prefix
                            _LOGGER.debug("Prefix %s assigned from model %s", model_prefix, model)
                            break
                    
                    device_details = None
                    if model in SUPPORTED_DEVICES:
                        _LOGGER.debug("Device %s found!", model)
                        device_details = SUPPORTED_DEVICES[model]
                    elif model_prefix is not None and model_prefix in SUPPORTED_DEVICES:
                        _LOGGER.debug("Device %s found! via prefix %s", model, model_prefix)
                        device_details = SUPPORTED_DEVICES[model_prefix]

                # If device_details is None at this point, we have an unknown device model.
                # Unsupported/Unknown Device.  Load the state, but store it in an "unsupported objects"
                # list for later use in diagnostics.
                device_class = None
                
                if device_details is not None:
                    device_class = _DREO_DEVICE_TYPE_TO_CLASS.get(device_details.device_type, None)
                else:
                    device_details = DreoDeviceDetails(device_type = DreoDeviceType.UNKNOWN)

                if device_class is None:
                    device_class = PyDreoUnknownDevice
                
                device : PyDreoBaseDevice = device_class(device_details, dev, self)

                self.load_device_state(device)

                self.devices.append(device)

                self._device_list_by_sn[device.serial_number] = device
            except UnknownModelError as ume:
                _LOGGER.warning("Unknown device model: %s", ume)
                _LOGGER.debug(dev)

        return True

    def load_devices(self) -> bool:
        """Load devices from API. This is called once upon initialization."""
        if not self.enabled:
            return False

        self.in_process = True
        proc_return = False

        response = None

        if self.debug_test_mode:
            _LOGGER.debug("Debug Test Mode is enabled.  Using test payload.")
            response = self.debug_test_mode_payload.get("get_devices", None)
        else:
            # Use pydreo-cloud SDK
            try:
                response = self._cloud_client.get_devices()
                _LOGGER.debug("Response: %s", Helpers.redactor(json.dumps(response, indent=2)))
            except Exception as e:
                _LOGGER.error("Error retrieving device list with pydreo-cloud SDK: %s", str(e))
                self.in_process = False
                return False

        # Stash the raw response for use by the diagnostics system, so we don't have to pull
        # logs
        self.raw_response = response

        if response:
            device_list = response
            proc_return = self._process_devices(device_list)
        else:
            _LOGGER.warning("Error retrieving device list")

        self.in_process = False

        return proc_return

    def load_device_state(self, device: PyDreoBaseDevice) -> bool:
        """Load device state from API. This is called once upon initialization for each supported device."""
        _LOGGER.debug("load_device_state: %s, enabled: %s", device.name, self.enabled)
        if not self.enabled:
            return False

        self.in_process = True
        proc_return = False

        response = None

        if self.debug_test_mode:
            _LOGGER.debug("Debug Test Mode is enabled.  Using test payload.")
            response = self.debug_test_mode_payload.get(device.serial_number, None)
        else:
            # Use pydreo-cloud SDK
            try:
                response = self._cloud_client.get_status(device.serial_number)
                _LOGGER.debug("Response: %s", Helpers.redactor(json.dumps(response, indent=2)))
            except Exception as e:
                _LOGGER.error("Error retrieving device state with pydreo-cloud SDK: %s", str(e))
                self.in_process = False
                return False

        # stash the raw return value from the devicestate api call
        device.raw_state = response

        if response:
            device_state = response
            device.update_state(device_state)
            proc_return = True
        else:
            _LOGGER.error("Error retrieving device state")

        self.in_process = False

        return proc_return

    def login(self) -> bool:
        """Return True if log in request succeeds."""

        if self.debug_test_mode:
            self.enabled = True
            _LOGGER.debug("Debug Test Mode is enabled.  Skipping login.")
            return True

        user_check = isinstance(self.username, str) and len(self.username) > 0
        pass_check = isinstance(self.password, str) and len(self.password) > 0
        if user_check is False:
            _LOGGER.error("Username invalid")
            return False
        if pass_check is False:
            _LOGGER.error("Password invalid")
            return False

        try:
            response = self._cloud_client.login()
            self.token = self._cloud_client.access_token

            # Parse region from token (format: "token:REGION")
            if ":" in self.token:
                token_parts = self.token.split(":")
                if len(token_parts) == 2:
                    region_suffix = token_parts[1].upper()
                    if region_suffix == "NA":
                        self.auth_region = DREO_AUTH_REGION_NA
                    elif region_suffix == "EU":
                        self.auth_region = DREO_AUTH_REGION_EU
                    _LOGGER.info("Dreo Auth reports user region as: %s", region_suffix)

            self.enabled = True
            _LOGGER.debug("Login successful with pydreo-cloud SDK")
            return True
        except Exception as e:
            _LOGGER.error("Error logging in with pydreo-cloud SDK: %s", str(e))
            return False

    def get_device_setting(self, device: PyDreoBaseDevice, setting : DreoDeviceSetting) -> bool | int:
        """Get a device setting from the API.

        Uses direct API call since pydreo-cloud SDK doesn't support settings endpoints.
        """
        if self.debug_test_mode:
            _LOGGER.warning("get_device_setting: Not available in debug test mode. "
                           "Device: %s, Setting: %s", device.name, setting)
            return None

        if not self._cloud_client or not self._cloud_client.endpoint or not self._cloud_client.access_token:
            _LOGGER.debug("get_device_setting: Client not authenticated or endpoint not available. "
                         "Device: %s, Setting: %s", device.name, setting)
            return None

        try:
            # Import Helpers from pydreo-cloud SDK
            from pydreo.helpers import Helpers

            # Clean token by removing region suffix
            clean_token = Helpers.clean_token(self._cloud_client.access_token)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {clean_token}",
                "UA": "openapi/1.0.0",
            }
            params = {
                "deviceSn": device.serial_number,
                "dataKey": setting,
                "timestamp": Helpers.timestamp(),
                "pydreover": "1.0.0",
            }

            response = Helpers.call_api(
                self._cloud_client.endpoint + "/api/user-device/setting",
                "get",
                headers,
                params
            )

            if response and "dataValue" in response:
                value_str = response["dataValue"]
                # Try to convert to int if possible
                try:
                    return int(value_str)
                except ValueError:
                    return value_str

            _LOGGER.debug("get_device_setting: No value returned for %s", setting)
            return None

        except Exception as e:
            _LOGGER.error("get_device_setting failed: %s", str(e))
            return None

    def set_device_setting(self, device: PyDreoBaseDevice, setting : DreoDeviceSetting, value : bool | int) -> None:
        """Set a device setting via the API.

        Uses direct API call since pydreo-cloud SDK doesn't support settings endpoints.
        """
        if self.debug_test_mode:
            _LOGGER.warning("set_device_setting: Not available in debug test mode. "
                           "Device: %s, Setting: %s, Value: %s", device.name, setting, value)
            return False

        if not self._cloud_client or not self._cloud_client.is_authenticated:
            _LOGGER.error("set_device_setting: Client not authenticated")
            return False

        try:
            import requests
            from pydreo.helpers import Helpers
            from pydreo.const import REQUEST_TIMEOUT

            # Clean token by removing region suffix
            clean_token = Helpers.clean_token(self._cloud_client.access_token)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {clean_token}",
                "UA": "openapi/1.0.0",
            }
            params = {
                "timestamp": Helpers.timestamp(),
                "pydreover": "1.0.0",
            }
            body = {
                "deviceSn": device.serial_number,
                "dataKey": setting,
                "dataValue": str(value),
            }

            # Make PUT request directly since Helpers.call_api doesn't support PUT
            response = requests.put(
                self._cloud_client.endpoint + "/api/user-device/setting",
                headers=headers,
                params=params,
                json=body,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                response_body = response.json()
                if response_body.get("code") == 0:
                    _LOGGER.debug("set_device_setting: Success")
                    return True
                else:
                    _LOGGER.error("set_device_setting: API error: %s", response_body.get("msg"))
                    return False
            else:
                _LOGGER.error("set_device_setting: HTTP error: %s", response.status_code)
                return False

        except Exception as e:
            _LOGGER.error("set_device_setting failed: %s", str(e))
            return False

    def start_transport(self) -> None:
        """Initialize the websocket and start transport"""
        if not self.debug_test_mode:
            self._transport.start_transport(self.api_server_region, self.token)

    def stop_transport(self) -> None:
        """Close down the transport socket"""
        if not self.debug_test_mode:
            self._transport.stop_transport()

    def testonly_interrupt_transport(self) -> None:
        """Close down the transport socket"""
        self._transport.testonly_interrupt_transport()

    def _transport_consume_message(self, message):
        _LOGGER.debug("pydreo._transport_consume_message: %s", message)

        message_device_sn = message["devicesn"]

        if message_device_sn in self._device_list_by_sn:
            device = self._device_list_by_sn[message_device_sn]
            device.handle_server_update_base(message)
        else:
            # Message is to an unknown device, log it out just in case...
            _LOGGER.debug(
                "Received message for unknown or unsupported device. SN: %s",
                message_device_sn,
            )
            _LOGGER.debug("Message: %s", message)

    def send_command(self, device: PyDreoBaseDevice, params) -> None:
        """Send a command to Dreo servers via REST API."""
        _LOGGER.debug("Sending command to device %s: %s", device.serial_number, params)

        if self.debug_test_mode:
            _LOGGER.debug("Debug Test Mode is enabled.  Pretending we received the message...")
            self._transport_consume_message({"devicesn": device.serial_number,
                                             "method": "report",
                                             "reported": params})
        else:
            # Use pydreo-cloud SDK to send command via REST API
            try:
                response = self._cloud_client.update_status(device.serial_number, **params)
                _LOGGER.debug("Command sent successfully: %s", response)
                # Update device state with the response
                if response:
                    device.update_state(response)
            except Exception as e:
                _LOGGER.error("Error sending command with pydreo-cloud SDK: %s", str(e))
