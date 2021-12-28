import base64
import hashlib
import sys
import threading
import time
from re import Pattern

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts
from utils.config import config as utils_config
from utils.config.config import CLI_COMMON_USER_NAME, CLI_COMMON_PASSWORD, CLI_COMMON_BOOTLOADER_TIMEOUT, \
    CLI_COMMON_REBOOT_TIMEOUT, CLI_COMMON_NORMAL_MODE_TIMEOUT, \
    CLI_COMMON_NETWORK_READY_TIMEOUT
from tests.common.common_const import CommonConst


class CliCommonUtil:
    __UBOOT_PUSHING_TIMEOUT = 0.5
    __WHERE_AM_I_CHECKING_TIMEOUT = 5
    __WAIT_AFTER_ENTER_UBOOT = 2
    __GET_MESSAGE_WAIT = 5
    __COMMAND_RESPONSE_TIMEOUT = 30

    """
    Boot device eMMC
    """
    BOOT_DEVICE_EMMC = "eMMC"
    """
    Boot device SD-Card
    """
    BOOT_DEVICE_SDCARD = "SD-Card"

    """
    Logged in the system
    """
    POSITION_LOGGED_IN = "logged in"
    """
    System waits credentials to be passed by user
    """
    POSITION_LOGIN = "login"
    """
    System  in bootloader mode
    """
    POSITION_UBOOT = "uboot"

    __util_lock = threading.Lock()
    __link_ready_event_eth = threading.Event()
    __link_ready_event_wlan = threading.Event()
    __link_ready_event_usb = threading.Event()

    def __callback_network_link_state(self, msg: str):
        if CliRegexConsts.REGEX_ETH0_NETWORK_READY.search(msg):
            self.__link_ready_event_eth.set()
            return
        if CliRegexConsts.REGEX_WLAN0_NETWORK_READY.search(msg):
            self.__link_ready_event_wlan.set()
            return
        if CliRegexConsts.REGEX_USB0_NETWORK_READY.search(msg):
            self.__link_ready_event_usb.set()
            return

    def __perform_command(self, command: str, timeout: float, expected_result: Pattern or list[Pattern]):
        self.__cli.flush_incoming_data()
        self.__cli.send_message(command)

        if isinstance(expected_result, Pattern):
            return self.__cli.get_message(timeout, expected_result) is not None
        elif isinstance(expected_result, list):
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    return None
                message = self.__cli.get_message(self.__GET_MESSAGE_WAIT)
                if message is None:
                    continue
                for regex in expected_result:
                    if regex.search(message) is not None:
                        return message

    def __start_watching_network_links_state(self):
        self.__link_ready_event_usb.clear()
        self.__link_ready_event_eth.clear()
        self.__link_ready_event_wlan.clear()
        self.__cli.register_message_callback(self.__callback_network_link_state,
                                             {CliRegexConsts.REGEX_ETH0_NETWORK_READY,
                                              CliRegexConsts.REGEX_WLAN0_NETWORK_READY,
                                              CliRegexConsts.REGEX_USB0_NETWORK_READY})

    def __stop_watching_network_links_state(self):
        self.__cli.unregister_message_callback(self.__callback_network_link_state)

    def __wait_for_network_links_ready(self):
        start_time = time.time()
        while True:
            if time.time() - start_time > CLI_COMMON_NETWORK_READY_TIMEOUT:
                # If wlan0 has no suitable AP configurations, "wlan0: link becomes ready" will not be occurred, so,
                # exit on timeout is ok in this case.
                # Any way, checking of "wlan0: link becomes ready" is required to be sure that the system will not
                # change settings of the wlan device while running some test case.
                # The similar situation with usb0. "link becomes ready" may not be occurred.
                break

            if self.__link_ready_event_usb.is_set() and self.__link_ready_event_wlan.is_set() and self.__link_ready_event_eth.is_set():
                # all the links are ready
                break

        self.__stop_watching_network_links_state()

    def __get_hash_from_mac(self, mac_addr_str: str, user: str, salt: str, hash_name: str) -> str or None:
        """
        Compose hash of user, mac address and salt.
        :param mac_addr_str: MAC address of UI board
        :param user:
        :param salt:
        :param hash_name:
        :return: str or none
        """
        str_to_hash = f"{user}{mac_addr_str}{salt}\n"
        if hash_name == "sha512":
            mac_hash = hashlib.sha512(str_to_hash.encode()).hexdigest()
            return base64.b64encode(mac_hash.encode()).decode()
        elif hash_name == "sha384":
            mac_hash = hashlib.sha384(str_to_hash.encode()).hexdigest()
            return base64.b64encode(mac_hash.encode()).decode()
        elif hash_name == "sha256":
            mac_hash = hashlib.sha256(str_to_hash.encode()).hexdigest()
            return base64.b64encode(mac_hash.encode()).decode()
        elif hash_name == "sha1":
            mac_hash = hashlib.sha1(str_to_hash.encode()).hexdigest()
            return base64.b64encode(mac_hash.encode()).decode()
        elif hash_name == "md5":
            mac_hash = hashlib.md5(str_to_hash.encode()).hexdigest()
            return base64.b64encode(mac_hash.encode()).decode()
        else:
            print(f"This hash '{hash_name}' is not supported")
            return

    def __init__(self, cli: DebugCLI, login: str = CLI_COMMON_USER_NAME, password: str = CLI_COMMON_PASSWORD):
        """
        Class constructor. Initialize the utility.
        :param cli: Debug CLI object.
        :param login: system username.
        :param password: password of the system user.
        """
        self.__login = login
        self.__password = password

        self.__cli = cli

    def login(self, wait_for_network_ready: bool = True) -> bool:
        """
        Performs logging in into the CLI of WB Common UI board. Returns the result of the function invocation.
        :param wait_for_network_ready: Wait for all the network links to be ready.
        :return: True on success, otherwise – False.
        """
        with self.__util_lock:
            if wait_for_network_ready:
                self.__start_watching_network_links_state()
            result = self.__perform_command(CliCommandConsts.COMMAND_CTRL_C, self.__COMMAND_RESPONSE_TIMEOUT,
                                            [CliRegexConsts.REGEX_LOGGED_IN, CliRegexConsts.REGEX_LOGIN])

            time.sleep(CommonConst.TIMEOUT_20_SEC)

            if result is None:
                print("login() no response after COMMAND_CTRL_C", file=sys.stderr)
                return False
            elif CliRegexConsts.REGEX_LOGGED_IN.search(result):
                if wait_for_network_ready:
                    self.__stop_watching_network_links_state()
                print("login() already logged in")
                return True

            result = self.__perform_command(self.__login, self.__COMMAND_RESPONSE_TIMEOUT,
                                            [CliRegexConsts.REGEX_LOGGED_IN, CliRegexConsts.REGEX_PASSWORD])
            if result is None:
                if wait_for_network_ready:
                    self.__stop_watching_network_links_state()
                print(f"login() no response after {self.__login}", file=sys.stderr)
                return False
            elif CliRegexConsts.REGEX_LOGGED_IN.search(result):
                print("login() successful without password")
                if wait_for_network_ready:
                    print("login() wait for network to be ready")
                    self.__wait_for_network_links_ready()
                    print("login() done")
                return True

            if self.__perform_command(self.__password, self.__COMMAND_RESPONSE_TIMEOUT,
                                      CliRegexConsts.REGEX_LOGGED_IN):
                print("login() successful")
                if wait_for_network_ready:
                    print("login() wait for network to be ready")
                    self.__wait_for_network_links_ready()
                    print("login() done")
                return True
            else:
                if wait_for_network_ready:
                    self.__stop_watching_network_links_state()
                print("login() no response after CLI_COMMON_PASSWORD", file=sys.stderr)
                return False

    def logout(self) -> bool:
        """
        Performs logging out from the CLI of WB Common UI board.
        :return: True on success, otherwise – False.
        """
        with self.__util_lock:
            result = self.__perform_command(CliCommandConsts.COMMAND_CTRL_C, self.__COMMAND_RESPONSE_TIMEOUT,
                                            [CliRegexConsts.REGEX_LOGGED_IN, CliRegexConsts.REGEX_LOGIN])
            if result is None:
                print("logout() no response after COMMAND_CTRL_C", file=sys.stderr)
                return False
            elif CliRegexConsts.REGEX_LOGIN.search(result):
                print("logout() already logged out")
                return True

            if self.__perform_command(CliCommandConsts.COMMAND_LOGOUT, self.__COMMAND_RESPONSE_TIMEOUT,
                                      CliRegexConsts.REGEX_LOGIN):
                print("logout() successful")
                return True
            else:
                print("logout() no response after COMMAND_LOGOUT", file=sys.stderr)
                return False

    def reboot(self, timeout: float = CLI_COMMON_REBOOT_TIMEOUT) -> bool:
        """
        Performs software reboot of WB Common UI board. Waits timeout before returning the result of the function
        invocation. Returns earlier if the required response has received from the board.
        :param timeout: timeout waiting for the function execution complete.
        :return: True on success, otherwise – False.
        """
        with self.__util_lock:
            if not self.__perform_command(CliCommandConsts.COMMAND_CTRL_C, self.__COMMAND_RESPONSE_TIMEOUT,
                                          CliRegexConsts.REGEX_LOGGED_IN):
                print("reboot() no response after COMMAND_CTRL_C", file=sys.stderr)
                return False

            if self.__perform_command(CliCommandConsts.COMMAND_REBOOT, timeout, CliRegexConsts.REGEX_LOGIN):
                print("reboot() successful")
                return True
            else:
                print("reboot() no response after COMMAND_REBOOT", file=sys.stderr)
                return False

    def reboot_to(self, boot_device: str, timeout: float = CLI_COMMON_REBOOT_TIMEOUT) -> bool:
        """
        Performs software reboot of WB Common UI board to concrete boot device. Waits timeout before returning the
        result of the function invocation. Returns earlier if the required response has received from the board.
        :param boot_device: Boot device to boot after system restart. Could be CliCommonUtil.BOOT_DEVICE_EMMC or
        CliCommonUtil.BOOT_DEVICE_SDCARD
        :param timeout: timeout waiting for the function execution complete.
        :return: True on success, otherwise – False.
        """
        with self.__util_lock:
            if self.switch_to_bootloader():
                # wait a couple of seconds to ensure that all the empty commands have reached the Common UI board
                # and the system processed them
                time.sleep(self.__WAIT_AFTER_ENTER_UBOOT)
                if boot_device == self.BOOT_DEVICE_EMMC:
                    self.__cli.send_message(CliCommandConsts.COMMAND_BOOT_FROM_EMMC)
                else:
                    self.__cli.send_message(CliCommandConsts.COMMAND_BOOT)

                if self.__cli.get_message(timeout, CliRegexConsts.REGEX_LOGIN):
                    print("reboot_to() successful")
                    return True
                else:
                    print("reboot_to() failed. Login string expected, but not found", file=sys.stderr)
                    return False
            else:
                print("reboot_to() failed. Could not switch to bootloader", file=sys.stderr)
                return False

    def switch_to_bootloader(self, timeout: float = CLI_COMMON_BOOTLOADER_TIMEOUT,
                             reboot_command: str = CliCommandConsts.COMMAND_REBOOT) -> bool:
        """
        Performs reboot of the WB Common UI board from Linux or from bootloader and stops at bootloader mode.
        Waits for according response from the board, after switching to the bootloader mode.
        Returns the result of the function invocation.
        :param timeout: timeout waiting for the function execution complete.
        :param reboot_command: command that should reboot the board:
                                "reboot" to reboot in Linux (default),
                                "reset" to reboot in bootloader,
                                "bmode emmc" to reboot in bootloader and boot from emmc.
        :return: True on success, otherwise – False.
        Note: As switching to bootloader is a functionality which requires fast reaction on the board state change,
        continuously pushing the empty command after reboot should be more robust approach to avoid missing moment, when
        the command should be sent to move to uboot.
        """
        command_start_time = time.time()
        self.__cli.flush_incoming_data()

        if reboot_command == CliCommandConsts.COMMAND_REBOOT:
            if not self.__perform_command(CliCommandConsts.COMMAND_CTRL_C, timeout, CliRegexConsts.REGEX_LOGGED_IN):
                print("switch_to_bootloader() failed. Maybe is not logged in", file=sys.stderr)
                return False
        else:
            if not self.__perform_command(CliCommandConsts.COMMAND_EMPTY, timeout, CliRegexConsts.REGEX_UBOOT_CLI):
                print("switch_to_bootloader() failed. Maybe is not in bootloader mode", file=sys.stderr)
                return False

        self.__cli.send_message(reboot_command)
        while True:
            if time.time() - command_start_time > timeout:
                print("switch_to_bootloader() failed. Timeout occurred on waiting uboot", file=sys.stderr)
                return False
            if self.__perform_command(CliCommandConsts.COMMAND_EMPTY, self.__UBOOT_PUSHING_TIMEOUT,
                                      CliRegexConsts.REGEX_UBOOT_CLI):
                break
        # wait a couple of seconds to ensure that all the empty commands have reached the Common UI board
        # and the system processed them
        time.sleep(self.__WAIT_AFTER_ENTER_UBOOT)

        return True

    def switch_to_normal_mode(self, timeout: float = CLI_COMMON_NORMAL_MODE_TIMEOUT) -> bool:
        """
        Performs switching WB Common UI board to normal mode from bootloader. Waits for according response from the
        board, after switching to the bootloader mode. Returns the result of the function execution.
        :param timeout: timeout waiting for the function execution complete.
        :return: True on success, otherwise – False.
        """
        with self.__util_lock:
            if not self.__perform_command(CliCommandConsts.COMMAND_CTRL_C, self.__COMMAND_RESPONSE_TIMEOUT,
                                          CliRegexConsts.REGEX_UBOOT_CLI):
                print("switch_to_normal_mode() no response after COMMAND_CTRL_C", file=sys.stderr)
                return False

            if self.__perform_command(CliCommandConsts.COMMAND_BOOT, timeout, CliRegexConsts.REGEX_LOGIN):
                print("switch_to_normal_mode() successful")
                return True
            else:
                print("switch_to_normal_mode() no response after COMMAND_BOOT", file=sys.stderr)
                return False

    def where_am_i(self, timeout: float):
        """
        The method checks where the CLI is now.
        :param timeout: timeout for waiting the recognition result
        :return: There are next possible results: POSITION_LOGIN, POSITION_LOGGED_IN, POSITION_UBOOT, or None
        """
        with self.__util_lock:
            command_start_time = time.time()

            self.__cli.flush_incoming_data()
            while True:
                self.__cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
                message = self.__cli.get_message(self.__WHERE_AM_I_CHECKING_TIMEOUT)

                if message is None:
                    continue
                if CliRegexConsts.REGEX_LOGIN.search(message):
                    return self.POSITION_LOGIN
                if CliRegexConsts.REGEX_LOGGED_IN.search(message):
                    return self.POSITION_LOGGED_IN
                if CliRegexConsts.REGEX_UBOOT_CLI.search(message):
                    return self.POSITION_UBOOT
                if time.time() - command_start_time > timeout:
                    break

            print("where_am_i() failed. Could not recognize position.", file=sys.stderr)
            return None

    def wait_for_links_ready_after_start(self):
        """
        Wait for links of eth0, wlan0 and usb0 network interfaces to be ready.
        Execution of this function is required after system boot complete to prevent undefined behavior due to
        high CPU loading during the links establishing.
        CliCommonUtil.login() API performs the waiting automatically if the related argument is not set on False
        """
        with self.__util_lock:
            self.__start_watching_network_links_state()
            self.__wait_for_network_links_ready()

    def get_password_from_mac_address(self, mac_address: str, user: str = CLI_COMMON_USER_NAME) -> str or None:
        """
        Extract password from MAC address of Common UI board.
        :param mac_address: MAC address of UI board
        :param user: 'root' or 'welbilt'
        :return: password string
        """
        salt = CommonConst.PASSCFG[user]["salt"]
        hash_name = CommonConst.PASSCFG[user]["hash"]
        pw_length = CommonConst.PASSCFG[user]["len"]
        full_hash = self.__get_hash_from_mac(mac_address, user, salt, hash_name)
        if full_hash:
            full_hash = full_hash.replace(" ", "@")
            return full_hash[:pw_length]
        else:
            return

    def update_login_credentials(self, user: str, password: str):
        """
        Update user name and password.
        :param user:
        :param password:
        :return:
        """
        utils_config.CLI_COMMON_USER_NAME = user
        utils_config.CLI_COMMON_PASSWORD = password
