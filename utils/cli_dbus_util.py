import queue
import sys
from collections import namedtuple

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts
from utils.common.dbus_func_consts import DbusFuncConsts
from utils.common.dbus_signal_consts import DbusSignalConsts
from utils.config.config import CLI_DBUS_SIGNAL_TIMEOUT, CLI_DBUS_FUNCTION_TIMEOUT, CLI_DBUS_SUBSCR_TIMEOUT, \
    CLI_DBUS_UNSUBSCR_TIMEOUT


class CliDbusUtil:
    DBusSignalResult = namedtuple("DBusSignalResult", ["signal", "result_list"])

    __RETURN_TYPE_BOOL = "boolean"
    __RETURN_TYPE_STRING = "string"
    __RETURN_BOOL_TRUE = "true"

    __SIGNALS_WITH_TWO_RESULTS = [DbusSignalConsts.NEW_PACKAGE_AVAILABLE,
                                  DbusSignalConsts.FORCED_PACKAGE_CHECKED,
                                  DbusSignalConsts.PACKAGE_UPDATE_STATE]

    __RETURN_REGEX_LIST_FUNCTIONS = {
        DbusFuncConsts.GET_CURR_PARTITION: CliRegexConsts.REGEX_DBUS_RESULT_PARTITION,
        DbusFuncConsts.GET_CURR_SW_VERSION: CliRegexConsts.REGEX_DBUS_RESULT_FW_VERSION,
        DbusFuncConsts.GET_ALT_SW_VERSION: CliRegexConsts.REGEX_DBUS_RESULT_FW_VERSION,
        DbusFuncConsts.SUSPEND_FW_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.RESUME_FW_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.REJECT_FW_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.FORCE_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.FORCE_FW_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.SWITCH_TO_ALT_FW: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.SUSPEND_PACKAGE_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.RESUME_PACKAGE_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.REJECT_PACKAGE_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.FORCE_PACKAGE_UPDATE: CliRegexConsts.REGEX_DBUS_RESULT_BOOL,
        DbusFuncConsts.GET_SW_VERSION: CliRegexConsts.REGEX_DBUS_RESULT_SW_VERSION,
        DbusFuncConsts.GET_CURRENT_BOOT_DEVICE: CliRegexConsts.REGEX_DBUS_RESULT_BOOT_DEV}

    __RETURN_REGEX_LIST_SIGNALS = {
        DbusSignalConsts.NEW_FIMWARE_AVAILABLE: [CliRegexConsts.REGEX_DBUS_RESULT_FW_VERSION],
        DbusSignalConsts.FORCED_FIRMWARE_CHECKED: [CliRegexConsts.REGEX_DBUS_RESULT_BOOL],
        DbusSignalConsts.FIRMWARE_UPDATE_STATE: [CliRegexConsts.REGEX_DBUS_RESULT_FW_UPDATE_STATE],
        DbusSignalConsts.FIRMWARE_CHECK_RESULTS: [CliRegexConsts.REGEX_DBUS_CHECK_RESULTS],
        DbusSignalConsts.NEW_PACKAGE_AVAILABLE:
            [CliRegexConsts.REGEX_DBUS_RESULT_PACK_NAME, CliRegexConsts.REGEX_DBUS_RESULT_FW_VERSION],
        DbusSignalConsts.FORCED_PACKAGE_CHECKED:
            [CliRegexConsts.REGEX_DBUS_RESULT_PACK_NAME, CliRegexConsts.REGEX_DBUS_RESULT_BOOL],
        DbusSignalConsts.PACKAGE_UPDATE_STATE:
            [CliRegexConsts.REGEX_DBUS_RESULT_PACK_NAME, CliRegexConsts.REGEX_DBUS_RESULT_PACKAGE_UPDATE_STATE],
        DbusSignalConsts.PACKAGE_CHECK_RESULTS: [CliRegexConsts.REGEX_DBUS_CHECK_RESULTS]}

    __expected_result_for_signal = None
    __expected_count_of_results = 0

    def __get_result_count_for_signal(self, signal: str):
        if signal in self.__SIGNALS_WITH_TWO_RESULTS:
            return 2
        else:
            return 1

    def __incoming_data_callback(self, msg: str):
        if CliRegexConsts.REGEX_DBUS_SIGNAL_STRING.search(msg):
            signal = self.__get_signal_from_string(msg)
            if signal is None:
                # signal is unknown of wrong message has passed
                return
            if signal in self.__signal_notification_dict.keys():
                self.__expected_count_of_results = self.__get_result_count_for_signal(signal)
                self.__expected_result_for_signal = self.DBusSignalResult(signal, [])
            return
        if CliRegexConsts.REGEX_DBUS_COMMON_RESULT.search(msg) and self.__expected_result_for_signal:
            for regex in self.__RETURN_REGEX_LIST_SIGNALS[self.__expected_result_for_signal.signal]:
                if regex.search(msg):
                    break
            self.__expected_result_for_signal.result_list.append(self.__get_result_from_string(msg))
            self.__expected_count_of_results -= 1
            if self.__expected_count_of_results == 0:
                self.__signal_queue.put(self.__expected_result_for_signal)
                self.__expected_result_for_signal = None
            return

    @staticmethod
    def __get_signal_from_string(string: str):
        search_result = CliRegexConsts.REGEX_DBUS_SIGNAL_MEMBER.search(string)
        if search_result:
            return search_result.group(0).lstrip(CliCommandConsts.DBUS_SIGNAL_COMMAND_MEMBER)
        else:
            return None

    @staticmethod
    def __put_signal_to_string(signal: str, string: str):
        signal_position = string.rfind(CliCommandConsts.DBUS_SIGNAL_COMMAND_MEMBER) + len(
            CliCommandConsts.DBUS_SIGNAL_COMMAND_MEMBER)
        if signal_position:
            return string[:signal_position] + signal + string[signal_position:]
        else:
            return None

    def __get_result_from_string(self, result_string):
        method_result = result_string.lstrip()
        if self.__RETURN_TYPE_BOOL in method_result:
            if self.__RETURN_BOOL_TRUE in method_result:
                return True
            else:
                return False
        elif self.__RETURN_TYPE_STRING in method_result:
            return method_result.strip("string").replace('\"', '').strip()

    def __init__(self, cli: DebugCLI):
        """
        Class constructor. Initialize the utility.
        :param cli: Debug CLI object
        """
        self.__cli = cli
        self.__signal_notification_dict = dict()
        self.__signal_queue = queue.Queue()
        self.__cli.register_message_callback(self.__incoming_data_callback, {CliRegexConsts.REGEX_DBUS_SIGNAL_STRING,
                                                                             CliRegexConsts.REGEX_DBUS_COMMON_RESULT})

    def subscribe_signal_notification(self, signal: str, timeout: float = CLI_DBUS_SUBSCR_TIMEOUT) -> bool:
        """
        Subscribes on D-Bus signal notification. After that, all the signal notifications will be placed into the queue
        and the user will be available to check them.
        :param timeout: signal subscription result waiting timeout
        :param signal: D-Bus signal to subscribe on.
        :return: True on success, False if the signal notification has already subscribed or some error occurred.
        """
        if signal in self.__signal_notification_dict:
            print("Has already subscribed on signal:" + signal, file=sys.stderr)
            return False

        command_string = self.__put_signal_to_string(signal, CliCommandConsts.COMMAND_DBUS_SIGNAL)
        self.__cli.flush_incoming_data()
        self.__cli.send_message(command_string)
        result = self.__cli.get_message(timeout, CliRegexConsts.REGEX_SIGNAL_SUBSCR_RESULT)

        if result is not None:
            dbus_monitor_process: str = CliRegexConsts.REGEX_DBUS_MONITOR_PROCESS.search(result).group(0)
            self.__signal_notification_dict[signal] = dbus_monitor_process
            return True
        else:
            print("Something went wrong during subscription on D-Bus signal: " + signal, file=sys.stderr)
            return False

    def unsubscribe_signal_notification(self, signal: str, timeout: float = CLI_DBUS_UNSUBSCR_TIMEOUT) -> bool:
        """
        Unsubscribes from D-Bus signal notification. After that, the signal notifications will not be placed into
        the queue.
        :param signal: D-Bus signal to unsubscribe.
        :param timeout: Timeout waiting for unsubscribing on the signal
        :return: True on success, False if the signal notification is not present in subscription list.
        """
        if signal not in self.__signal_notification_dict:
            print("No subscription found for signal:" + signal, file=sys.stderr)
            return False

        self.__cli.flush_incoming_data()
        self.__cli.send_message(CliCommandConsts.COMMAND_PS_WITH_GREP + self.__signal_notification_dict[signal])

        if self.__cli.get_message(timeout, CliRegexConsts.REGEX_DBUS_MONITOR) is not None:
            command_string = CliCommandConsts.COMMAND_KILL + self.__signal_notification_dict[signal]
            self.__cli.send_message(command_string)
            self.__cli.get_message(timeout, CliRegexConsts.REGEX_LOGGED_IN)
        self.__signal_notification_dict.pop(signal)
        return True

    def clear_subscription_list(self):
        """
        Clear signal subscription list with unsubscribing on those signals
        """
        for subscription in list(self.__signal_notification_dict):
            self.unsubscribe_signal_notification(subscription)

    def run_method(self, method: str, parameter: str = None,
                   timeout: float = CLI_DBUS_FUNCTION_TIMEOUT, expected_return: bool = True) -> str or None:
        """
        Runs D-Bus function using Debug CLI. Could take string parameter to pass with the function. Returns function
        execution result.
        :param method: method to be invoked.
        :param parameter: string parameter to be passed together with the method. By default is None.
        :param timeout: result waiting timeout in seconds.
        :param expected_return: Flag which represents does the method should returns some result.
        :return: Returns None if there is no result of the function executed or timeout has occurred. Otherwise –
        returns function execution result string. If expected_return is False - always returns None without delay.
        """
        command_string = CliCommandConsts.COMMAND_DBUS_METHOD + method

        if parameter:
            command_string += " string:\"" + parameter + "\""

        self.__cli.flush_incoming_data()
        self.__cli.send_message(command_string)

        if not expected_return:
            return None

        method_result_regex = self.__RETURN_REGEX_LIST_FUNCTIONS[method]
        if method_result_regex is None:
            print("run_method. No return regex from method: " + method, file=sys.stderr)
            return None

        method_result: str = self.__cli.get_message(timeout, method_result_regex)
        if method_result:
            method_result = method_result.lstrip()
            return self.__get_result_from_string(method_result)
        else:
            print("Something went wrong. No response from method: " + method, file=sys.stderr)
            return None

    def get_signal(self, timeout: float = CLI_DBUS_SIGNAL_TIMEOUT) -> str or None:
        """
        Performs getting D-Bus signals notifications, on which has subscribed before. If timeout is non-zero,
        the method blocks for required time for waiting a signal notification from the board.
        :param timeout: timeout waiting for available signal notifications in message queue. Represents time in seconds.
        :return: None if nothing to read from message queue, or timeout occurred.
        Otherwise – returns signal notification string in format "Signal: *SIGNAL_NAME*; Result: *RESULT*".
        """
        try:
            return self.__signal_queue.get(True, timeout)
        except queue.Empty:
            return None

    def clear_signal_list(self):
        """
        Clear signal list
        """
        while True:
            try:
                self.__signal_queue.get(block=False)
            except queue.Empty:
                break
