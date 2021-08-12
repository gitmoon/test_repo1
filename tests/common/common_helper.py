import re
import sys
import time
from re import Pattern

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts


class CommonHelper:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @staticmethod
    def copy_file(source_file, target_path):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_CP + source_file + " " + target_path)
        while True:
            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)
            if not message:
                continue
            if CommonRegex.PATH_FILE_NOT_FOUND.search(message):
                print("copy_file(). No file/path found on the storage device", file=sys.stderr)
                return False
            if CliRegexConsts.REGEX_LOGGED_IN.search(message):
                print("copy_file() done for " + source_file)
                return True

    @staticmethod
    def remove_file(filename, forced=False, recursive=False, timeout=CommonConst.TIMEOUT_10_SEC):
        command = CommonConst.COMMAND_RM
        if forced:
            command += CommonConst.RM_ARGUMENT_FORCED
        if recursive:
            command += CommonConst.RM_ARGUMENT_RECURSIVE
        command += filename

        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(command)
        while True:
            message = CommonHelper.__debug_cli.get_message(timeout)
            if not message:
                continue
            if CommonRegex.PATH_FILE_NOT_FOUND.search(message):
                print(f"Cannot remove '{filename}': no such file", file=sys.stderr)
                return False
            if CliRegexConsts.REGEX_LOGGED_IN.search(message):
                print(f"File '{filename}' removed successfully")
                return True

    @staticmethod
    def list_directory(directory):
        command = f'{CommonConst.COMMAND_LS}{directory}'
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(command)
        start_time = time.time()
        while True:
            if time.time() - start_time > CommonConst.TIMEOUT_60_SEC:
                return None

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                           CommonRegex.LIST_DIR_COMMAND_RESULT)
            if not message:
                continue
            else:
                return message

    @staticmethod
    def switch_ethernet(state: bool):
        CommonHelper.__debug_cli.flush_incoming_data()

        if state:
            CommonHelper.__debug_cli.send_message("ifconfig eth0 up")
            assert CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.ETH0_READY)
        else:
            CommonHelper.__debug_cli.send_message("ifconfig eth0 down")
            assert CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

    @staticmethod
    def wifi_radio_on():
        CommonHelper.__debug_cli.flush_incoming_data()

        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_WIFI_RADIO_ON)
        assert CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

    @staticmethod
    def switch_wifi(state: bool):
        CommonHelper.__debug_cli.flush_incoming_data()

        if state:
            CommonHelper.__debug_cli.send_message(
                CommonConst.COMMAND_IFCONFIG + f"{CommonConst.IFACE_WIFI} {CommonConst.IFACE_STATE_UP}")
            # If wlan0 has no suitable AP configurations, "wlan0: link becomes ready" will not be occurred.
            # Any way, checking of "wlan0: link becomes ready" is required to be sure that the system is
            # completely configured the wlan device
            CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.WLAN0_READY)
        else:
            CommonHelper.__debug_cli.send_message(
                CommonConst.COMMAND_IFCONFIG + f"{CommonConst.IFACE_WIFI} {CommonConst.IFACE_STATE_DOWN}")
            CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

    @staticmethod
    def wifi_connect(ssid, password, timeout):
        CommonHelper.__debug_cli.flush_incoming_data()

        test_start_time = time.time()
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_WIFI_CONNECT + f"{ssid} password \"{password}\"")
        while True:
            if time.time() - test_start_time > timeout:
                print("wifi_connect() timeout occurred", file=sys.stderr)
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)
            if message is None:
                continue

            if CommonRegex.WLAN_ACTIVATED.search(message):
                print("wifi_connect() successfully connected to: " + ssid)
                return True
            if CommonRegex.WLAN_SSID_NOT_FOUND.search(message):
                print("wifi_connect() ssid is not found: " + ssid, file=sys.stderr)
                return False
            if CommonRegex.WLAN_CONN_FAILED.search(message):
                print("wifi_connect() connection failed with : " + message, file=sys.stderr)
                return False

    @staticmethod
    def wifi_disconnect(ssid):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_WIFI_DISCONNECT + ssid)
        assert CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

    @staticmethod
    def set_wlan_tx_power(power):
        output_command = f"{CommonConst.COMMAND_IW}{CommonConst.IFACE_WIFI} {CommonConst.IW_SET_TXPOWER}{power}"

        start_time = time.time()
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(output_command)
        while True:
            if time.time() - start_time > CommonConst.TIMEOUT_30_SEC:
                print("__set_wlan_tx_power() timeout occurred", file=sys.stderr)
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)

            if CommonRegex.IW_ERROR.search(message):
                print("__set_wlan_tx_power() execution error", file=sys.stderr)
                return False
            if CliRegexConsts.REGEX_LOGGED_IN.search(message):
                return True

    @staticmethod
    def wifi_check_connection():
        connection_ssid = None

        CommonHelper.__debug_cli.flush_incoming_data()
        result_searching_start_time = time.time()
        CommonHelper.__debug_cli.send_message(
            f"{CommonConst.COMMAND_IW}{CommonConst.IW_DEV}{CommonConst.IFACE_WIFI} {CommonConst.IW_LINK}")
        while True:
            if time.time() - result_searching_start_time > CommonConst.TIMEOUT_20_SEC:
                print("__wifi_check_connection() unknown ping result, timeout occurred", file=sys.stderr)
                return None

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC)
            if message is None:
                continue

            if CommonRegex.IW_LINK_SSID.search(message):
                connection_ssid = message.split(": ")[1]
            if connection_ssid is not None and CliRegexConsts.REGEX_LOGGED_IN.search(message):
                break

        return connection_ssid

    @staticmethod
    def ping(host, ping_time):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_PING + host)
        time.sleep(ping_time)

        result_searching_start_time = time.time()
        CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
        while True:
            if time.time() - result_searching_start_time > CommonConst.TIMEOUT_20_SEC:
                print("ping() unknown ping result, timeout occurred", file=sys.stderr)
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC)
            if message is None:
                continue

            if CommonRegex.BAD_PING.search(message):
                print("ping() return state False")
                return False
            if CommonRegex.GOOD_PING.search(message):
                print("ping() return state True")
                return True

    @staticmethod
    def check_package_presence(package: str):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_TYPE + package)
        type_result = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, re.compile(f"{package} {CommonConst.TYPE_PACKAGE_IS}"))

        if type_result is None:
            print("__check_package_presence() unsuccessful. No response on \'type\' command", file=sys.stderr)
            return False
        else:
            return True

    @staticmethod
    def check_package_help(package: str, help_argument: str):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(package + help_argument)
        if CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.COMMAND_NOT_FOUND) is None:
            return True
        else:
            print("__check_package_help() unsuccessful. \'Command not found\' occurred", file=sys.stderr)
            return False

    @staticmethod
    def check_package_version(package: str, version_argument: str, result_regex: Pattern):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(package + version_argument)
        if CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, result_regex) is not None:
            return True
        else:
            print("__check_package_version() unsuccessful", file=sys.stderr)
            return False

    @staticmethod
    def perform_ethtool(device: str, speed: str, duplex: str, auto_negotiation: str):
        check_speed = False
        check_duplex = False
        check_autoneg = False

        ethtool_command = f"{CommonConst.COMMAND_ETHTOOL}-s {device} speed {speed} duplex {duplex} autoneg {auto_negotiation}"

        CommonHelper.__debug_cli.flush_incoming_data()

        test_start_time = time.time()
        CommonHelper.__debug_cli.send_message(ethtool_command)
        # wait some time ensure that the function is done and the device is completely reconfigured
        time.sleep(CommonConst.TIMEOUT_10_SEC)

        ethtool_check_command = f"{CommonConst.COMMAND_ETHTOOL}{device}"
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(ethtool_check_command)
        while True:
            if time.time() - test_start_time > CommonConst.TIMEOUT_60_SEC:
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)
            if message is None:
                continue

            result = CommonRegex.ETHTOOL_SPEED.search(message)
            if result:
                if speed in result.group(0):
                    check_speed = True
                else:
                    print("__perform_ethtool() failed to set speed: " + speed, file=sys.stderr)
                    return False

            result = CommonRegex.ETHTOOL_DUPLEX.search(message)
            if result:
                if duplex in result.group(0).lower():
                    check_duplex = True
                else:
                    print("__perform_ethtool() failed to set duplex: " + duplex, file=sys.stderr)
                    return False

            result = CommonRegex.ETHTOOL_AUTONEG.search(message)
            if result:
                if auto_negotiation in result.group(0):
                    check_autoneg = True
                else:
                    print("__perform_ethtool() failed to set autoneg: " + auto_negotiation, file=sys.stderr)
                    return False

            if check_speed and check_duplex and check_autoneg:
                return True

    @staticmethod
    def find_matches(command_to_perform: str, matches_regex: Pattern, timeout: int):
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(command_to_perform)
        found_list = []
        test_start_time = time.time()
        while True:
            if time.time() - test_start_time > timeout:
                break

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC)
            if message is None:
                continue
            elif matches_regex.search(message):
                found_list.append(message)

        return found_list

    @staticmethod
    def configure_can(iface: str, enable: bool, bit_rate: int = 20000):
        CommonHelper.__debug_cli.flush_incoming_data()
        if enable:
            CommonHelper.__debug_cli.send_message(
                f"{CommonConst.COMMAND_IP_LINK}{CommonConst.IP_LINK_SET}{iface} {CommonConst.IFACE_STATE_UP} {CommonConst.IP_LINK_TYPE_CAN}{CommonConst.IP_LINK_BITRATE}{bit_rate}")
        else:
            CommonHelper.__debug_cli.send_message(
                f"{CommonConst.COMMAND_IP_LINK}{CommonConst.IP_LINK_SET}{iface} {CommonConst.IFACE_STATE_DOWN}")

        return_state = True
        test_start_time = time.time()
        while True:
            if time.time() - test_start_time > CommonConst.TIMEOUT_30_SEC:
                print("__configure_can() timeout occurred", file=sys.stderr)
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC)
            if message is None:
                continue
            elif CliRegexConsts.REGEX_LOGGED_IN.search(message):
                return return_state
            elif CommonRegex.CAN_DEV_BUSY.search(message):
                print("__configure_can() Device or resource busy", file=sys.stderr)
                return_state = False

    @staticmethod
    def perform_cangen(iface: str, extended_id: bool, data: bytes, id: int, delay_msec: int, generation_time_sec: int,
                       additional_arguments: str = None):
        output_command = f"{CommonConst.COMMAND_CANGEN} {iface} "

        if extended_id:
            output_command += CommonConst.CANGEN_EXTENDED

        data_len = len(data)
        if data_len == 0 or data_len > CommonConst.CAN_MAX_PAYLOAD:
            return False

        output_command += f"{CommonConst.CANGEN_DATA_LEN}{data_len} {CommonConst.CANGEN_DATA}{data.hex().upper()} "
        output_command += f"{CommonConst.CANGEN_ID}{hex(id).upper()} "
        output_command += f"{CommonConst.CANGEN_INTERVAL} {delay_msec} "

        if additional_arguments:
            output_command += additional_arguments

        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(output_command)
        time.sleep(generation_time_sec)

        CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
        return CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                    CliRegexConsts.REGEX_LOGGED_IN) is not None

    @staticmethod
    def run_from_emmc_after_reboot():
        print("run_from_emmc_after_reboot()")
        command_start_time = time.time()
        CommonHelper.__debug_cli.flush_incoming_data()

        while True:
            if time.time() - command_start_time > CommonConst.TIMEOUT_4_MIN:
                assert False
            CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            if CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_500_MSEC, CliRegexConsts.REGEX_UBOOT_CLI):
                break
        CommonHelper.boot_from_emmc()

    @staticmethod
    def boot_from_emmc():
        print("boot_from_emmc()")
        CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_BOOT_FROM_EMMC)
        assert CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN)

    @staticmethod
    def reboot_to_emmc():
        print("reboot_to_emmc()")
        CommonHelper.__cli_common_util.switch_to_bootloader()
        CommonHelper.boot_from_emmc()

    @staticmethod
    def create_folder(folder: str, with_patents: bool = False):
        CommonHelper.__debug_cli.flush_incoming_data()

        command = CommonConst.COMMAND_MKDIR
        if with_patents:
            command += CommonConst.MKDIR_ARGUMENT_P
        command += folder

        return_state = True
        test_start_time = time.time()
        CommonHelper.__debug_cli.send_message(command)
        while True:
            if time.time() - test_start_time > CommonConst.TIMEOUT_60_SEC:
                print("create_folder() timeout occurred", file=sys.stderr)
                return False

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)
            if message is None:
                continue

            if CommonRegex.MKDIR_ERROR.search(message):
                print(f"create_folder() error while creating {folder}", file=sys.stderr)
                return_state = False
            if CliRegexConsts.REGEX_LOGGED_IN.search(message):
                print(f"create_folder() done for {folder}")
                return return_state

    @staticmethod
    def get_md5_checksum(file):
        command = f'{CommonConst.COMMAND_MD5_CHECKSUM} {file}'
        CommonHelper.__debug_cli.flush_incoming_data()
        CommonHelper.__debug_cli.send_message(command)

        start_time = time.time()
        while True:
            if time.time() - start_time > CommonConst.TIMEOUT_60_SEC:
                return None

            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                           CommonRegex.MD5_CHECKSUM_COMMAND_RESULT)
            if not message:
                continue
            else:
                return message.split(" ")[0]

    @staticmethod
    def hard_reset(boot_from_emmc=False):
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_ECHO + CommonConst.SET_SYSRQ)
        CommonHelper.__debug_cli.send_message(CommonConst.COMMAND_ECHO + CommonConst.SET_SYSRQ_TRIGG)

        if boot_from_emmc:
            command_start_time = time.time()
            CommonHelper.__debug_cli.flush_incoming_data()
            while True:
                if time.time() - command_start_time > CommonConst.TIMEOUT_60_SEC:
                    print("Boot system after hard reset failed. Timeout occurred", file=sys.stderr)
                    return False
                CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
                if CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_500_MSEC, CliRegexConsts.REGEX_UBOOT_CLI):
                    break
            CommonHelper.__debug_cli.send_message(CliCommandConsts.COMMAND_BOOT_FROM_EMMC)

        command_start_time = time.time()
        CommonHelper.__debug_cli.flush_incoming_data()
        while True:  # Wait system to boot after hard reset
            if time.time() - command_start_time > CommonConst.TIMEOUT_60_SEC:
                print("Boot system after hard reset failed. Timeout occurred", file=sys.stderr)
                return False
            message = CommonHelper.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGIN)
            if message:
                print("Boot system after hard reset succeeded.")
                return True
