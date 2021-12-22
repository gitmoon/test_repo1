import re
from re import Pattern


class CliRegexConsts:
    REGEX_LOGGED_IN: Pattern = re.compile(r'root@welbilt-common-ui43:.+#|welbilt-common-ui43:.+$')
    REGEX_LOGGED_IN2: Pattern = re.compile(r'^root@welbilt-common-ui43:.#.$')
    REGEX_LOGIN: Pattern = re.compile(r'welbilt-common-ui43 login:')
    REGEX_PASSWORD: Pattern = re.compile(r"Password:")
    REGEX_STOP_AUTOBOOT: Pattern = re.compile(
        r"U-Boot \d{4}\.\d{2}-Welbilt\+\w+ \(\w{3} \d{2} \d{4} - \d\d:\d\d:\d\d .\d+\)")
    REGEX_UBOOT_CLI: Pattern = re.compile(r"=>")
    REGEX_SIGNAL_SUBSCR_RESULT: Pattern = re.compile(r"\[\d+] \d+")
    REGEX_DBUS_MONITOR_PROCESS: Pattern = re.compile(r"\d+$")
    REGEX_DBUS_COMMON_RESULT: Pattern = re.compile(r"(boolean|string) (\".+\"|true|false)")
    REGEX_DBUS_SIGNAL_STRING: Pattern = re.compile(
        r"(signal time=.+ sender=:.+ -> destination=.+ serial=.+ path=/instance; interface=org\.welbilt\.firmwaremanager\.FirmwareInterface;)? member=\w+")
    REGEX_DBUS_SIGNAL_MEMBER: Pattern = re.compile(r"member=\w+")
    REGEX_DBUS_MONITOR: Pattern = re.compile(r"\d+ \w+  \d+:\d+:\d+ dbus-monitor")
    REGEX_DBUS_RESULT_BOOL: Pattern = re.compile(r"boolean (true|false)")
    REGEX_DBUS_RESULT_PARTITION: Pattern = re.compile(r"string \"(A|B)\"")
    REGEX_DBUS_RESULT_FW_VERSION: Pattern = re.compile(r"string \"(\d+|Undefined)\"")
    REGEX_DBUS_RESULT_SW_VERSION: Pattern = re.compile(r"string \"\d+\.\d+\"")
    REGEX_DBUS_RESULT_BOOT_DEV: Pattern = re.compile(r"string \"(eMMC|SD-card)\"")
    REGEX_DBUS_RESULT_PACK_NAME: Pattern = re.compile(r"string \".+\"")
    REGEX_DBUS_RESULT_FW_UPDATE_STATE = re.compile(
        r"string \"(Kernel Update Started|RootFs Update Started|Switching To New Firmware|Partition Unmount Failed|Partition Mount Failed|Firmware Extraction Failed|Kernel Update Failed)\"")
    REGEX_DBUS_RESULT_PACKAGE_UPDATE_STATE = re.compile(
        r"string \"(System Backup Started|Kernel Partition Backup Failed|RootFS Partition Backup Failed|System Update Started|Package Extraction Failed|Chmod Failed|Prescript Execution Failed|Copying Failed|Postscript Execution Failed)\"")
    REGEX_USB0_NETWORK_READY = re.compile(r"usb0: link becomes ready")
    REGEX_ETH0_NETWORK_READY = re.compile(r"eth0: link becomes ready")
    REGEX_WLAN0_NETWORK_READY = re.compile(r"wlan0: link becomes ready")
    REGEX_DBUS_CHECK_RESULTS = re.compile(
        r"string \"(Success|Package Broken|Incomplete Package|Invalid Signature|Compatibility Check Failed|Same Version)\"")
    ROOT_FS_UPDATE_PROGRESS = re.compile(r"RootFs Update \d{1,3}%")
    SYSTEM_BACKUP_PROGRESS = re.compile(r"System Backup \d{1,3}%")
    CHECK_RESULTS_SIGNALS = re.compile(r"packageCheckResults|firmwareCheckResults")
    REGEX_FOUND_FILE = re.compile(r"^found$")
