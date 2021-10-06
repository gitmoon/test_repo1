"""
Common configuration constants
"""
# could be "Development", "Production" or "Slim"
TEST_BUILD_TYPE = "Production"

# required for "2.7. Reset", "2.8. Ethernet", "2.9. Wi-Fi", "2.10. Networking"
TEST_HOST_IP_ADDR = "109.86.196.215"
# required for "2.7. Reset", "2.9. Wi-Fi"
WIFI_SSID = "ssid"
# required for "2.7. Reset", "2.9. Wi-Fi"
WIFI_PASS = "pass"

"""
2.5. EMMC
"""
USB_DEVICE_NAME = "sda3"  # USB flash drive device name
TEST_FILE = "100MB.bin"  # Test file name for read and write operations
HOME_DIR = "/home/root"  # Home directory
TEMP_DIR = "/temp"  # Temporary directory
EMULATED_FLASH_DRIVE_PATH = f"/run/media/mmcblk0p4/emulated_flash/{USB_DEVICE_NAME}"
#TEST_FILE_PATH = "/run/media/mmcblk0p4/flash_data/emmc"

"""
2.10. Networking
"""
# if the next ports are accessible, could be left unchanged
NETWORKING_TCP_PORT = 65432
NETWORKING_UDP_PORT = 65431

"""
2.12. Serial Ports
"""
# converter should be wired as for full duplex mode
RS_485_PORT_FULL_DUPLEX = "COM1"
# converter should be wired as for half duplex mode
RS_485_PORT_HALF_DUPLEX = "COM1"

"""
2.26. Firmware Update
"""
FLASH_DRIVE_PATH = "/run/media/mmcblk0p4/emulated_flash/sda2"
FW_SOURCE_PATH = "/run/media/mmcblk0p4/flash_data/bsp_update"

# could be left unchanged, if there is no necessity to change files hierarchy
FW_FILE_PATH_ON_FLASH = f"{FW_SOURCE_PATH}/common/"
FW_FILE_PATH_ON_FLASH_CORRUPTED = f"{FW_SOURCE_PATH}/corrupted/"
FW_FILE_PATH_ON_FLASH_MISS_FILE = f"{FW_SOURCE_PATH}/miss_file/"
FW_FILE_PATH_ON_FLASH_BAD_KERNEL = f"{FW_SOURCE_PATH}/bad_kernel/"
FW_FILE_PATH_ON_FLASH_WO_PACKAGES = f"{FW_SOURCE_PATH}/wo_packages/"
PACKAGE_FILE_PATH_ON_FLASH = f"{FW_SOURCE_PATH}/package/"

"""
2.27. U-boot Bootloader
"""
BOARD_ID = 2
PANEL_ID = 7  # 7 for 7-inch board and 6 for 10-inch board
BOARD_IP_ADDR = "0.0.0.0"
INCORRECT_IP_ADDR = "0.0.0.0"

