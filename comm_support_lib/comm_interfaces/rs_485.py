from collections.abc import Callable

from comm_support_lib.config.config import *
from comm_support_lib.hw_drivers.serial_driver import SerialDriver


class RS485:
    def __init__(self, port: str, rate: int, parity: str, stop_bit: int,
                 ic_timeout: float = RS_485_INTERCHAR_TIMEOUT, msg_timeout: float = RS_485_MSG_TIMEOUT):
        """
        Class constructor. Initialize object during its creation.
        :param rate: baud rate of the RS-485 serial converter
        :param parity: parity settings for the RS-485 serial converter
        :param stop_bit: stop bit settings for the RS-485 serial converter. could be one of the next values: 1, 1.5, 2.
        :param port: port of the RS-485 serial converter.
        :param ic_timeout: inter-char timeout, helps to avoid inter-frame gap.
        :param msg_timeout: timeout between messages in seconds.
        """
        self.__bus = SerialDriver(port, rate, ic_timeout, msg_timeout, parity=parity,
                                  stopbits=stop_bit)

    def update_serial_config(self, rate: int, parity: str, stop_bit: int) -> None:
        """
        Update configuration of serial port including baud rate, parity and stop bit configs.
        :param rate: baud rate of the RS-485 serial converter.
        :param parity: parity settings for the RS-485 serial converter.
        :param stop_bit: stop bit settings for the RS-485 serial converter
        """
        self.__bus.update_port_config(rate, parity, stop_bit)

    def send_message(self, msg: bytes) -> None:
        """
        Performs message sending to RS-485 through serial converter.
        :param msg: message to be sent to the board
        """
        self.__bus.send_message(msg)

    def get_message(self, timeout: float) -> bytes or None:
        """
        Performs getting message from RS-485 h/w interface using serial converter.
        :param timeout: timeout waiting for available data in message queue.
        :return: None if nothing to read from message queue, or timeout occurred. Otherwise – byte array of the message.
        """
        return self.__bus.get_message(timeout)

    def get_parameters(self) -> dict:
        """
        Returns parameters of RS-485 serial converter. Return type is Dict.
        :return: Dictionary with parameters of RS-485 serial converter,
        {‘port’, ‘baud_rate’, ‘msg_timeout’, ‘parity’, ‘stopbits’}.
        """
        return self.__bus.get_parameters()

    def flush_incoming_data(self) -> None:
        """
        Clears incoming data queue. Could be useful between test cases running to minimize impact of previous tests on
        the current test.
        """
        self.__bus.flush_incoming_data()

    def register_message_callback(self, callback: Callable[bytes]) -> None:
        """
        Registers callback function to the list inside the RS-485 driver module. All the registered functions will be
        called when an incoming message will be received. If the callback function is already present in the list,
        the method will do nothing.
        :param callback: function to be placed into the list of incoming data callbacks
        """
        self.__bus.register_message_callback(callback)

    def unregister_message_callback(self, callback: Callable[bytes]) -> None:
        """
        Removes callback function of incoming data from the list inside RS-485 driver module. If there is no such
        function presents, the method will do nothing.
        :param callback: function to be removed from the list of incoming data callbacks
        """
        self.__bus.unregister_message_callback(callback)

    def clear_callback_list(self) -> None:
        """
        Remove all the functions, placed in the list of incoming data callbacks. Could be useful between test cases
        running to minimize impact of previous tests on the current test.
        """
        self.__bus.clear_callback_list()
