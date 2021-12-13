from tests.config.config import USB_DEVICE_NAME


class CommonConst:
    TIMEOUT_500_MSEC = 0.5
    TIMEOUT_2_SEC = 2
    TIMEOUT_5_SEC = 5
    TIMEOUT_10_SEC = 10
    TIMEOUT_20_SEC = 20
    TIMEOUT_30_SEC = 30
    TIMEOUT_55_SEC = 55
    TIMEOUT_60_SEC = 60
    TIMEOUT_4_MIN = 240
    TIMEOUT_15_MIN = 900
    TIMEOUT_25_MIN = 1500
    COMMAND_KERNEL_VERSION = "uname -r"
    MINIMAL_KERNEL_VERSION = 3000  # 3.0.00
    MIN_DRAM_SIZE = 128000  # 128 Mb
    MIN_GPU_MEM_SIZE = 64000000  # 64 Mb
    I2C_DEV_EEPROM = "2"
    I2C_DEV_FRAM = "3"
    CURRENT_I2C_DEV = "Current bus is "
    HEX_AA = "aa"
    HEX_BB = "bb"
    TEST_ENV_VAR_NAME = "test_var"
    TEST_ENV_VAR_VALUE = "123"
    COMMAND_TYPE = "type "
    COMMAND_PACKAGE_GPG = "gpg"
    COMMAND_PACKAGE_GPG_HELP = " --help"
    COMMAND_FIND_LIBDBUS = "find / -iname \"libdbus*\""
    COMMAND_LS_TRUETYPE = "ls /usr/share/fonts/truetype/"
    COMMAND_UBOOT_MMC_INFO = "mmc info"
    COMMAND_USB_MOUNT_POINT = f"mount | grep /dev/{USB_DEVICE_NAME} | awk '{{print $3}}'"
    COMMAND_CP = "cp "
    COMMAND_LS = "ls "
    COMMAND_MD5_CHECKSUM = "md5sum"
    COMMAND_RM = "rm "
    RM_ARGUMENT_FORCED = "-f "
    RM_ARGUMENT_RECURSIVE = "-r "
    COMMAND_DRAM_SIZE = "dmesg | grep Memory:|awk -F/ '{print $2}'| awk '{print $1}'"
    COMMAND_GPU_MEM_SIZE = "cat /sys/kernel/debug/gc/meminfo"
    COMMAND_DATE = "date"
    COMMAND_IFCONFIG = "ifconfig "
    COMMAND_WIFI_RADIO_ON = "nmcli r wifi on"
    COMMAND_WIFI_CONNECT = "nmcli d wifi connect "
    COMMAND_WIFI_DISCONNECT = "nmcli con down "
    COMMAND_PING = "ping "
    COMMAND_ECHO = "echo "
    SET_SYSRQ = "1 > /proc/sys/kernel/sysrq"
    SET_SYSRQ_TRIGG = "b > /proc/sysrq-trigger"
    IFACE_STATE_UP = "up"
    IFACE_STATE_DOWN = "down"
    IFACE_ETH = "eth0"
    IFACE_WIFI = "wlan0"
    COMMAND_CAT = "cat "
    TEST_PHRASE = "The quick brown fox jumps over the lazy dog"
    COMMAND_NC = "nc "
    NC_ARGUMENT_CHECK_TCP_CONNECTION = "-zv "
    NC_ARGUMENT_UDP = "-u "
    COMMAND_UDHCPC_CHECK = "udhcpc -i "
    RESOLV_CONF_FILE = "/etc/resolv.conf"
    COMMAND_IP_ROUTE = "ip route"
    COMMAND_IPTABLES = "iptables "
    COMMAND_NMCLI = "nmcli "
    HELP_ARGUMENT = " --help"
    VERSION_ARGUMENT = " --version"
    COMMAND_CHECK_AVAHI_DAEMON_SERVICE = "systemctl list-units --all | grep avahi-daemon"
    COMMAND_SSH = "ssh "
    SSH_VERSION_ARGUMENT = " -V"
    COMMAND_ETHTOOL = "ethtool "
    COMMAND_I2C = "i2c "
    COMMAND_HEXDUMP = "hexdump "
    HEXDUMP_READ_MAC_FROM_EEPROM = "-s 250 -n 6 /sys/bus/i2c/devices/2-0050/eeprom"
    I2C_SET_DEV_2 = "dev 2"
    I2C_READ_MAC_FROM_EEPROM = "md 0x50 fa.1 6"
    HWADDR_STRING = "HWaddr "
    ETH_MAC = "fw_printenv ethaddr"
    UDHCPC_ARGUMENT_COUNT_30 = " -t 30"
    TTY_RS485 = "/dev/ttyS1"
    PACKAGE_SETSERIAL = "setserial"
    SETSERIAL_ARGUMENT_VERSION = " -V"
    RS485_DEFAULT_BAUD = 115200
    RS485_FULL_DUPLEX = "0"
    RS485_HALF_DUPLEX = "1"
    SYS_FS_GPIO_EXPORT = "/sys/class/gpio/export"
    SYS_FS_GPIO_UNEXPORT = "/sys/class/gpio/unexport"
    SYS_FS_RS485_DUPLEX_PIN = "32"
    SYS_FS_RS485_DUPLEX_DIRECTION = f"/sys/class/gpio/gpio{SYS_FS_RS485_DUPLEX_PIN}/direction"
    SYS_FS_RS485_DUPLEX_VALUE = f"/sys/class/gpio/gpio{SYS_FS_RS485_DUPLEX_PIN}/value"
    SYS_FS_DIRECTION_OUT = "out"
    BUSYBOX_STTY_F = "busybox stty -F "
    STTY_F = "stty -F "
    STTY_ARGUMENT_SPEED = "speed"
    BUSYBOX_STTY_ARGUMENT_RS485 = "rs485"
    BUSYBOX_STTY_ARGUMENT_RTSONSEND = "rs485rtsonsend"
    BUSYBOX_STTY_ARGUMENT_RTSAFTERSEND = "rs485rtsaftersend"
    RS485_EOL = "\r"
    TEST_PHRASE_SHORT = "This is test"
    ALL_VOLTAGE_CHANNELS = " /sys/bus/iio/devices/iio:device0/in_voltage*_channel*_raw"
    VOLTAGE_CHANNEL_COUNT = 4
    BOARD_TEMPERATURE_FILE = " /sys/class/hwmon/hwmon0/temp1_input"
    SYSTEM_TEMPERATURE_RANGE = range(20000, 80000)
    PACKAGE_GDB = "gdb"
    PACKAGE_VALGRIND = "valgrind"
    COMMAND_UBOOT_SET_IP_ADDR = "setenv ipaddr "
    COMMAND_UBOOT_I2C = "i2c "
    COMMAND_UBOOT_DEV = "dev "
    COMMAND_UBOOT_MD = "md 0x50 10.1 02"
    COMMAND_UBOOT_MW = "mw 0x50 10.1 "
    COMMAND_UBOOT_PRINTENV = "printenv "
    COMMAND_UBOOT_SETENV = "setenv "
    COMMAND_UBOOT_SAVEENV = "saveenv"
    COMMAND_UBOOT_ENV_DELETE = "env delete "
    LIBQT5_ALL_FILES = "/usr/lib/libQt5*"
    LIBEGL_ALL_FILES = "/usr/lib/libEGL*"
    LIBGLESV2_ALL_FILES = "/usr/lib/libGLESv2*"
    GRAPHIC_EFFECTS_PATH = "/usr/lib/qml/QtGraphicalEffects"
    USR_LIB_QML_GREP_QML = "/usr/lib/qml | grep Qml"
    USR_LIB_QML_GREP_QUICK = "/usr/lib/qml | grep Quick"
    LIBQT5_GREP_SERIALPORT = "/usr/lib/libQt5* | grep SerialPort"
    LIBQT5DBUS_ALL_FILES = "/usr/lib/libQt5DBus*"
    COMMAND_FIND = "find "
    FIND_LIBGSTREAMER = "/ -iname \"libgstreamer-1.0.so.0\""
    COMMAND_FBSET = "fbset"
    BACKLIGHT_POWER_FILE = "/sys/class/backlight/backlight/bl_power"
    ADC_VALUE_RANGE = range(0, 4096)
    ALL_ADC_RAW_VALUES = "/sys/bus/iio/devices/iio\:device1/*raw"
    CAN_DEFAULT_BAUD = 1000000
    CAN_TEST_ID_EXTENDED = 0x11223344
    CAN_TEST_ID = 0xAB
    CAN_TEST_ID_STRING = "132"
    CAN_PAYLOAD = [0x11, 0x22, 0x33, 0x44, 0xDE, 0xAD, 0xBE, 0xEF]
    CAN_INTERFACE = "can0"
    CANGEN_DELAY = 500
    COMMAND_IP_LINK = "ip link "
    IP_LINK_SET = "set "
    IP_LINK_TYPE_CAN = "type can "
    IP_LINK_BITRATE = "bitrate "
    CANGEN_EXTENDED = "-e "
    CANGEN_DATA_LEN = "-L"
    CANGEN_DATA = "-D "
    CANGEN_ID = "-I"
    CANGEN_INTERVAL = "-g "
    CAN_MAX_PAYLOAD = 8
    COMMAND_CANGEN = "cangen"
    COMMAND_CANSEND = "cansend "
    COMMAND_CANDUMP = "candump "
    PARAM_LIST_FIELD_ID = "id"
    PARAM_LIST_FIELD_EXTENDED = "extended"
    PARAM_LIST_FIELD_BAUD = "baud_rate"
    WB_FIRMWARE_USB_PATH = "/welbilt/firmware/"
    WB_PACKAGE_USB_PATH = "/welbilt/package/"
    MEDIA_PATH = "/media/"
    USBSTORAGE_PATH = "/media/usbstorage/"
    EMULATED_FLASH = f"sda2"
    COMMAND_MKDIR = "mkdir "
    MKDIR_ARGUMENT_P = "-p "
    COMMAND_LN_S = "ln -s "
    FW_PCKG_PATH_ON_SDCARD = "/run/media/mmcblk0p4/"
    PARTITION_A = "/run/media/mmcblk0p2"
    PARTITION_B = "/run/media/mmcblk0p3"
    ETC_VERSION = "/etc/version"
    PROC_VERSION = "/proc/version"
    BSP_VERSION = "~/jabil/VERSION"
    LAST_SIGNAL_FOR_CORRUPTED_CASE = "forcedFirmwareChecked"
    FW_FILE_NAME = "welbilt-firmware-image-welbilt-common-ui43.tar"
    FW_FILE_NAME_INVALID_SIG = "welbilt-firmware-imx6sxsabresd_invalid_sig.tar"
    TEST_VERSION_MIN = 80000000000000
    TEST_VERSION_MAX = 99999999999999
    HW_MANAGER_PACKAGE = "hardware-manager"
    HW_MANAGER_NAME = "hardware-manager-1.0-r0_update.tar"
    HW_MANAGER_NAME_NO_PACKAGE = "hardware-manager-1.0-r0_update_no_package.tar"
    HW_MANAGER_NAME_NOT_COMPATIBLE = "hardware-manager-1.0-r0_update_not_compatible.tar"
    HW_MANAGER_NAME_INVALID_SIG = "hardware-manager-1.0-r0_update_invalid_sig.tar"
    HW_MANAGER_NAME_BROKEN = "hardware-manager-1.0-r0_update_broken.tar"
    SCREENGRABBER_PACKAGE = "screengrabber"
    SCREENGRABBER_NAME = "screengrabber-1.0-r0_update.tar"
    PACKAGE_PATH = "/opt/firmware_manager/packages/"
    HARDWARE_MANAGER_VERSION_PATH = PACKAGE_PATH + "hardware-manager-1.0-r0/version.txt"
    SCREENGRABBER_VERSION_PATH = PACKAGE_PATH + "screengrabber-1.0-r0/version.txt"
    PACKAGE_VERSION_FILE = "version.txt"
    BOOT_DEVICE_SDCARD = "SD-card"
    COMMAND_RESET = "reset"
    PREFIX_ALL = "*"
    PACKAGE_WPA_SUPPLICANT = "wpa_supplicant"
    PACKAGE_IWSPY = "iwspy"
    PACKAGE_IWPRIV = "iwpriv"
    COMMAND_LSMOD = "lsmod "
    LSMOD_GREP_ATH10K = "| grep ath10k"
    COMMAND_IW = "iw "
    IW_SET_TXPOWER = "set txpower "
    IW_DEV = "dev "
    IW_LINK = "link"
    IW_POWER_1DBM = "fixed 100"
    IW_POWER_15DBM = "fixed 1500"
    IW_POWER_20DBM = "fixed 2000"
    IW_POWER_AUTO = "auto"
    COMMAND_IWCONFIG = "iwconfig "
    IW_REG_SET = "reg set "
    IW_REG_GET = "reg get"
    WIFI_REGION_GB = "GB"
    WIFI_REGION_US = "US"
    COMMAND_IWLIST = "iwlist "
    IWLIST_FREQUENCY = "frequency"
    LSMOD_GREP_BTWILINK = "| grep btwilink"
    COMMAND_DMESG = "dmesg "
    DMESG_GREP_RTC = "| grep rtc"
    DMESG_GREP_TAS_AUDIO = "| grep 5720"
    LS_ALSA_LIB_ALL = "/usr/lib/alsa-lib/*"
    FIND_ALSA_MODULES_ALL = "/ -name \"libasound_module_*.so\""
    COMMAND_PRINTENV = "printenv "
    FDT_FILE = "fdt_file"
    COMMAND_RUN = "run "
    RUN_FINDFDT = "findfdt"
    TEST_NUMBER_RANGE_MIN = 1000000
    TEST_NUMBER_RANGE_MAX = 9999999
    EEPROM_FILE = "/sys/bus/i2c/drivers/at24/1-0050/eeprom"
    HEXDUMP_C = "-C "
    FILE_USB_HOST_ROLE = "/sys/kernel/debug/ci_hdrc.1/role"
    FILE_USB_OTG_ROLE = "/sys/kernel/debug/ci_hdrc.0/role"
    USB_ROLE_HOST = "host"
    USB_ROLE_GADGET = "gadget"
    COMMAND_HCICONFIG = "hciconfig "
    IFACE_HCI0 = "hci0"
    HCICONFIG_PISCAN = "piscan"
    TYPE_PACKAGE_IS = r"is .+"
    FILE_MODEL_NUMBER = "modelNumber.txt"
    FILE_MODEL_NUMBER_CONTENT_TEST = "TestBoard_0.0.1"
    FILE_MODEL_NUMBER_CONTENT_COMMONUI = "CommonUI_0.0.1"
    CHECK_RESULTS_SUCCESS = "Success"
    CHECK_RESULTS_PACKAGE_BROKEN = "Package Broken"
    CHECK_RESULTS_INCOMPLETE_PACKAGE = "Incomplete Package"
    CHECK_RESULTS_INVALID_SIGNATURE = "Invalid Signature"
    CHECK_RESULTS_COMPATIBILITY_FAILED = "Compatibility Check Failed"
    CHECK_RESULTS_SAME_VERSION = "Same Version"
    CHECK_FW_MANGER_LOG = "/opt/firmware_manager/bin/firmware_manager.log"
    BOOL_FALSE = "false"
    BOOL_TRUE = "true"
    KERNEL_UPDATE_STARTED = "Kernel Update Started"
    ROOTFS_UPDATE_STARTED = "RootFs Update Started"
    ROOTFS_UPDATE_PROGRESS_100 = "RootFs Update 100%"
    SYSTEM_BACKUP_UPDATE_PROGRESS_100 = "System Backup 100%"
    UNDEFINED = "Undefined"
    PASSCFG = {
        "root": {
            "salt": "jw7nEL8KFVblkmh3",
            "hash": "sha256",
            "len": 10
        },
        "welbilt": {
            "salt": "sc2fdfKFfds5ewww",
            "hash": "sha512",
            "len": 10
        }
    }
    USER_ROOT = "root"
    USER_WELBILT = "welbilt"
    COMMAND_WHOAMI = "whoami"
    COMMAND_SSHD_SOCKET_START = "systemctl start sshd.socket"
    MEDIA_SERVICE = "/media/service"
    FOUND_FILE = "found"
    COMMAND_PACKAGE_REMOVE = "opkg remove "
