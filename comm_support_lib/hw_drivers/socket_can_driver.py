import queue
import sys
import threading
import time

import can_socket
import serial  # to handle exceptions


class SocketCanDriver:
    def __init__(self, socket: str, baud_rate: int, msg_timeout: float):
        """
        Initialize CAN bus communication:
            Parameters:
                socket (str): CAN socket
                baud_rate (int):    Bus baud rate
                msg_timeout (float):  Timeout between messages (inter-frame gap)
        """
        self.__socket = socket
        self.__baud_rate = baud_rate
        self.__msg_timeout = msg_timeout
        self.__queue = queue.Queue(0)
        self.__clb_list = []
        self.__clb_list_lock = threading.Lock()
        self.__stop_polling_thread = threading.Event()

        self.__init_bus()

    def __del__(self):
        self.__close_bus()

    def __init_bus(self):
        """
        Initializes CAN interface. Creates polling thread.
        """
        try:
            self.__stop_polling_thread.clear()
            self.__bus = can_socket.interface.Bus(bustype='slcan', channel=self.__socket, rtscts=True, bitrate=self.__baud_rate)
            self.__pollingThread = threading.Thread(
                target=self.__poll_messages,
                daemon=True
            )
            self.__pollingThread.start()
        except serial.serialutil.SerialException as CANEx:
            print("Failed to initialize CAN Bus: {}".format(CANEx), file=sys.stderr)
            sys.exit(1)
        except Exception as ex:
            self.__bus.shutdown()
            print("Failed initialize CANBus bus_interface: {}".format(ex), file=sys.stderr)
            sys.exit(1)

    def __close_bus(self):
        """
        Stops polling thread and closes CAN interface
        """
        self.__stop_polling_thread.set()
        self.__pollingThread.join()
        try:
            self.__bus.shutdown()
        except Exception as ex:
            print("Failed to close CAN Bus: {}".format(ex), file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def __get_dict_from_message(msg: can_socket.Message):
        return {'id': msg.arbitration_id,
                'payload': msg.data}

    def __poll_messages(self):
        """
            Message polling function
        """
        while not self.__stop_polling_thread.is_set():
            try:
                msg = self.__bus.recv(self.__msg_timeout)
                # nothing is received
                if msg is None:
                    continue
                msg = self.__get_dict_from_message(msg)
                # execute callbacks from the list
                with self.__clb_list_lock:
                    if len(self.__clb_list):
                        for callback in self.__clb_list:
                            callback(msg)
                # put new message into the queue
                self.__queue.put(msg)
            except serial.serialutil.SerialException as CANEx:
                print("Failed to read message from CAN: {}".format(CANEx), file=sys.stderr)
            except queue.Full:
                print("CAN queue is full. Message lost", file=sys.stderr)

    def send_message(self, message_id: int, payload=None, is_extended_id: bool = False):
        """
        Send message to CAN bus_interface
            Parameters:
                message_id:    Message ID to send
                payload (bytes or list):   Message payload
                is_extended_id (bool): if message_id is extended, should be True
            Returns:
                status (bool): True if message has been sent successfully, False otherwise
        """
        if payload is None:
            payload = []
        try:
            msg = can_socket.Message(arbitration_id=message_id, data=payload, is_extended_id=is_extended_id)
            self.__bus.send(msg)
        except serial.serialutil.SerialException as ex:
            print("Failed to send message through CAN bus: {}".format(ex), file=sys.stderr)
            return False
        return True

    def get_message(self, timeout: float):
        """
        Get message from CAN bus_interface
            Parameters:
                timeout (float):  Operation timeout in seconds
            Returns:
                msg (bytearray): Received message (None if timeout expired)
        """
        try:
            msg = self.__queue.get(block=True, timeout=timeout)
            return msg
        except queue.Empty:
            return None

    def get_parameters(self):
        """
            Get Serial bus_interface parameters
                Returns:
                    parameters (dict): CAN Bus parameters
        """
        return {'socket': self.__socket,
                'baud_rate': self.__baud_rate,
                'msg_timeout': self.__msg_timeout}

    def flush_incoming_data(self):
        """
            Flush incoming data queue
        """
        while True:
            try:
                self.__queue.get(block=False)
            except queue.Empty:
                break

    def register_message_callback(self, callback):
        """
            Register incoming data callback
                Parameters:
                    callback (Callable): function to register as callback
        """
        if callback is None:
            print("register_message_callback(). Callback function is None", file=sys.stderr)
            return
        if callback in self.__clb_list:
            print("register_message_callback(). Callback function has already registered:" + callback.__name__,
                  file=sys.stderr)
            return
        with self.__clb_list_lock:
            self.__clb_list.append(callback)

    def unregister_message_callback(self, callback):
        """
            Unregister incoming data callback
                Parameters:
                    callback (Callable): callback function to unregister
        """
        if callback is None:
            print("unregister_message_callback(). Callback function is None", file=sys.stderr)
            return
        if callback not in self.__clb_list:
            print("Callback function is not registered:" + callback.__name__, file=sys.stderr)
            return
        with self.__clb_list_lock:
            self.__clb_list.remove(callback)

    def clear_callback_list(self):
        """
            Clear list of incoming data callbacks
        """
        with self.__clb_list_lock:
            self.__clb_list.clear()

    def update_iface_config(self, baud_rate: int):
        """
            Update configuration of Serial hardware interface
                Parameters:
                    baud_rate (int):    Baud rate of the bus
        """
        self.__close_bus()

        self.__baud_rate = baud_rate
        self.__init_bus()
