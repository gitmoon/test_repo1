import queue
import re
import sys
import time
from collections.abc import Callable
from re import Pattern
from threading import Lock

from comm_support_lib.common.meta_singleton import MetaSingleton
from comm_support_lib.config.config import *
from comm_support_lib.hw_drivers.serial_driver import SerialDriver


class DebugCLI(metaclass=MetaSingleton):
    __INCOMING_DATA_SPLIT_REGEX = re.compile(r'\r\n|\r')
    __DEBUG = True

    __REGEX_LOGGED_IN: Pattern = re.compile(r'root@welbilt-common-ui43:.+# $')
    __REGEX_UBOOT_CLI: Pattern = re.compile(r"=> $")
    __REGEX_LOGIN: Pattern = re.compile(r'welbilt-common-ui43 login: $')
    __REGEX_PASSWORD: Pattern = re.compile(r"Password: $")

    def __log_incoming_data(self, data_list):
        print("DebugCLI receive. Time: " + str(time.time()) + "; Data: " + str(data_list), file=sys.stderr)

    last_string = None

    def __parse_incoming_data(self, msg: bytes):
        message_string_list = []

        if len(msg) == 0:
            if self.last_string:
                message_string_list.append(self.last_string)
                self.last_string = None
            return message_string_list
        else:
            decoded_data = msg.decode("utf-8", "ignore")
            message_string_list = self.__INCOMING_DATA_SPLIT_REGEX.split(decoded_data)

            if self.last_string:
                message_string_list[0] = self.last_string + message_string_list[0]
                self.last_string = None

            if not decoded_data.endswith("\r") and not decoded_data.endswith("\r\n") and not (
                    self.__REGEX_LOGGED_IN.search(message_string_list[-1]) or self.__REGEX_UBOOT_CLI.search(
                message_string_list[-1]) or self.__REGEX_LOGIN.search(
                message_string_list[-1]) or self.__REGEX_PASSWORD.search(message_string_list[-1])):
                self.last_string = message_string_list.pop()
            return message_string_list

    def __incoming_message_callback(self, msg: bytes):
        message_string_list = self.__parse_incoming_data(msg)

        if len(message_string_list) == 0:
            return

        if self.__DEBUG:
            self.__log_incoming_data(message_string_list)

        for message_string in message_string_list:
            # skip message
            with self.__skip_list_lock:
                if any(regex.search(message_string) for regex in self.__skip_list):
                    continue
            # check for suitable callbacks
            with self.__message_callback_dict_lock:
                for callback in self.__message_callback_dict:
                    var = self.__message_callback_dict[callback]
                    if len(var) == 0:
                        callback(message_string)
                    else:
                        if any(regex.search(message_string) for regex in var):
                            callback(message_string)
            # add message into data queue
            self.__incoming_data_queue.put(message_string)

    def __init__(self, mode: str = None, ic_timeout: float = DEBUG_CLI_INTERCHAR_TIMEOUT,
                 msg_timeout: float = DEBUG_CLI_MSG_TIMEOUT):
        """
        Class constructor. Initialize object during its creation. As Debug CLI implemented using Singleton design
        pattern, the method is being called only once.
        :param mode: Debug CLI h/w interface mode. Could be “Serial” of “SSH”.
        :param ic_timeout: inter-char timeout, helps to avoid inter-frame gap.
        :param msg_timeout: timeout between messages in seconds (inter-frame gap).
        """
        if mode is None or mode == "Serial":
            self.__bus = SerialDriver(DEBUG_CLI_SERIAL_PORT, DEBUG_CLI_SERIAL_BAUD, ic_timeout=ic_timeout,
                                      msg_timeout=msg_timeout, enqueue_incoming_data=False)
        else:
            # here will be implementation of SSH interface
            pass

        self.__skip_list_lock = Lock()
        self.__skip_list = set()
        self.__message_callback_dict_lock = Lock()
        self.__message_callback_dict = {}
        self.__incoming_data_queue = queue.Queue(0)

        self.__bus.register_message_callback(self.__incoming_message_callback)

    def send_message(self, msg: str, eol: str = "\n") -> None:
        """
        Performs message sending to CLI of Welbilt Common UI board.
        :param msg: Message to be sent to the board.
        :param eol: End Of Line symbol. By default is "\n"
        """
        if self.__DEBUG:
            print("send_message(): " + msg)

        self.__bus.send_message((msg + eol).encode())

    def get_message(self, timeout: float, expected_str: Pattern = None) -> str or None:
        """
        Performs getting message from CLI of Welbilt Common UI board. If timeout is non-zero, the method blocks for
        required time for waiting a data from the board.
        :param timeout: Timeout waiting for available data in message queue. Represents time in seconds.
        :param expected_str: message string which will be returned if it will be found in incoming data queue. By
        default is None, what means that any existing message, present in data queue will be returned.
        :return: None if nothing to read from message queue, timeout occurred or expected_str was set, but was not
        found. Otherwise – message string.
        """
        if expected_str is None:
            try:
                return self.__incoming_data_queue.get(True, timeout)
            except queue.Empty:
                return None

        start_time = time.time()
        while True:
            try:
                msg_string = self.__incoming_data_queue.get(True, timeout)
                if msg_string is not None and expected_str.search(msg_string):
                    return msg_string
            except queue.Empty:
                # Do nothing. Just check timeout further.
                pass
            if (time.time() - start_time) > timeout:
                return None

    def get_parameters(self) -> dict:
        """
        Returns parameters of Debug CLI h/w driver. Return type is Dict.
        :return: -	Dictionary with parameters of Debug CLI h/w driver. For “Serial” mode it will
        contain - {‘port’, ‘baud_rate’, ‘msg_timeout’}, for “SSH” mode – {‘host’, ‘port’, ‘msg_timeout’}
        """
        return self.__bus.get_parameters()

    def flush_incoming_data(self) -> None:
        """
        Clears incoming data queue. Could be useful between test cases running to minimize impact of previous tests
        on the current test.
        """
        while True:
            try:
                self.__incoming_data_queue.get(block=False)
            except queue.Empty:
                break

    def register_message_callback(self, callback: Callable[str], expected_str: Pattern or set = None) -> None:
        """
        Registers callback function to the list inside the Debug CLI module. All the registered functions will be
        called when an incoming message will be received. If the callback function is already present in the list,
        the method will do nothing. If a filter for specific messages is set, the callback will be called only for
        those messages. Callback function should have the next argument format: def clb(msg: str).
        :param callback: function to be placed into the list of incoming data callbacks
        :param expected_str: represents regex or list of such regexes, on which the callback will be invoked. If None,
        the callback will be invoking for all the incoming messages.
        """
        with self.__message_callback_dict_lock:
            if expected_str is None:
                self.__message_callback_dict[callback] = set()
                return

            expected_str_list = self.__message_callback_dict.get(callback)

            if expected_str_list is None:
                if type(expected_str) is Pattern:
                    self.__message_callback_dict[callback] = {expected_str}
                else:
                    self.__message_callback_dict[callback] = set(expected_str)
            else:
                if type(expected_str) is Pattern:
                    self.__message_callback_dict[callback].add(expected_str)
                else:
                    self.__message_callback_dict[callback].update(expected_str)

    def unregister_message_callback(self, callback: Callable[str], expected_str: Pattern or set = None) -> None:
        """
        Removes incoming data callback function of from the callback list inside Debug CLI module. If there is no such
        function presents, the method will do nothing. If a filter for specific messages is set, the method will remove
        the callback invocation only for those messages.
        :param callback: function to be removed from the list of incoming data callbacks
        :param expected_str: represents regex or list of such regexes, for which the method invocation should be
        stopped. If None, the callback will be fully removed from the callback list.
        """
        with self.__message_callback_dict_lock:
            if callback not in self.__message_callback_dict:
                return

            if expected_str is None:
                self.__message_callback_dict.pop(callback)
                return

            if type(expected_str) is Pattern:
                self.__message_callback_dict[callback].remove(expected_str)
            else:
                self.__message_callback_dict[callback] -= expected_str

            if len(self.__message_callback_dict[callback]) == 0:
                self.__message_callback_dict.pop(callback)

    def clear_callback_list(self) -> None:
        """
        Remove all the functions, placed in the list of incoming data callbacks. Could be useful between test cases
        running to minimize impact of previous tests on the current test.
        """
        self.__bus.clear_callback_list()

    def message_skip_list_add(self, regex: Pattern or set) -> None:
        """
        Add message string or list of message strings to skip list. The messages will not be appeared in incoming data
        queue and callbacks will not be invoked on those messages.
        :param regex: patterns of incoming data to be skipped. Represents regex of set of regexes.
        """
        with self.__skip_list_lock:
            if type(regex) is Pattern:
                self.__skip_list.add(regex)
            else:
                self.__skip_list |= regex

    def message_skip_list_remove(self, regex: Pattern or set) -> None:
        """
        Remove message string or list of message strings from skip list. After the function processing, the messages
        will be appearing in incoming data queue and callbacks will be invoking on those messages in normal mode.
        :param regex: pattern of incoming data to be removed from skip list. Represents regex of set of regexes.
        """
        with self.__skip_list_lock:
            if type(regex) is Pattern:
                try:
                    self.__skip_list.remove(regex)
                except ValueError:
                    print("No record found for: " + regex, file=sys.stderr)
            else:
                self.__skip_list -= regex

    def message_skip_list_clear(self) -> None:
        """
        Clear the skip list of incoming messages.
        """
        with self.__skip_list_lock:
            self.__skip_list.clear()
