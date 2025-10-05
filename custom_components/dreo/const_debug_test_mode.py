
"""Debug test mode constants for the Dreo Home Assistant integration.

This module contains configuration constants used for debugging and testing
the Dreo integration without making actual API calls to the Dreo servers.

Constants:
    DEBUG_TEST_MODE: Boolean flag to enable/disable debug test mode
    DEBUG_TEST_MODE_DIRECTORY_NAME: Directory name for test data files
    DEBUG_TEST_MODE_DEVICES_FILE_NAME: Filename for device test data
"""

DEBUG_TEST_MODE : bool = False
# Uncomment to enable test mode.
# Tests will not pass if this is set to True to prevent accidental commits.
# DEBUG_TEST_MODE = True
DEBUG_TEST_MODE_DIRECTORY_NAME = "e2e_test_data"
DEBUG_TEST_MODE_DEVICES_FILE_NAME = "get_devices.json"
