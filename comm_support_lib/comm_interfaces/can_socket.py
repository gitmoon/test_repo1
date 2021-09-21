from collections.abc import Callable

from comm_support_lib.config.config import CAN_SOCKET, CAN_MSG_TIMEOUT
from comm_support_lib.hw_drivers.socket_can_driver import SocketCanDriver


class CAN:
    INPUT_DATA_FIELD_ID = "id"
    INPUT_DATA_FIELD_PAYLOAD = "payload"

    def __init__(self, rate: int, socket: str = CAN_SOCKET, timeout: float = CAN_MSG_TIMEOUT):
        """
        Class constructor. Initialize object during its creation.
        :param rate: network host name and port of the SocketCAN converter.
        :param socket: baud rate of the CAN interface.
        :param timeout: timeout between messages in seconds.
        """
        self.__bus = SocketCanDriver(socket, rate, timeout)

    def update_iface_config(self, rate: int) -> None:
        """
        Update configuration of CAN interface.
        :param rate: baud rate of the CAN interface.
        """
        self.__bus.update_iface_config(rate)

    def send_message(self, message_id: int, payload: bytes = None, is_extended_id: bool = False) -> None:
        """
        Performs message sending to CAN interface.
        :param message_id: CAN message will be sent with this message ID.
        :param payload: CAN message payload.
        :param is_extended_id: if message_id is extended, should be True
        """
        self.__bus.send_message(message_id, payload, is_extended_id=is_extended_id)

    def get_message(self, timeout: float) -> dict or None:
        """
        Performs getting message from CAN interface. If timeout is non-zero,
        the method blocks for required time for waiting a data from the board.
        :param timeout: timeout waiting for available data in message queue.
        :return: None if nothing to read from message queue, or timeout occurred. Otherwise – byte array of the message.
        """
        return self.__bus.get_message(timeout)

    def get_parameters(self) -> dict:
        """
        Returns parameters of SocketCAN driver module. Return type is Dict.
        :return: Dictionary with parameters of SocketCAN driver module, {‘socket’, ‘baud_rate’, ‘msg_timeout’}.
        """
        return self.__bus.get_parameters()

    def flush_incoming_data(self) -> None:
        """
        Clears incoming data queue. Could be useful between test cases running to minimize impact of previous tests
        on the current test.
        """
        self.__bus.flush_incoming_data()

    def register_message_callback(self, callback: Callable[dict]) -> None:
        """
        Registers callback function to the list inside the SocketCAN driver module. All the registered functions will
        be called when an incoming message will be received. If the callback function is already present in the list,
        the method will do nothing.
        :param callback: function to be placed into the list of incoming data callbacks.
        """
        self.__bus.register_message_callback(callback)

    def unregister_message_callback(self, callback: Callable[dict]) -> None:
        """
        Removes callback function of incoming data from the list inside SocketCAN driver module. If there is no such
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
