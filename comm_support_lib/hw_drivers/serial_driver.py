import queue
import sys
import threading
from threading import Lock

import serial

from comm_support_lib.common.serial_base_interface import SerialBaseInterface
from comm_support_lib.common.serial_iface_parity_consts import SerialIfaceParityConsts

SERIAL_MESSAGE_MAX_BYTES = 1024 * 8  # 8kB


class SerialDriver(SerialBaseInterface):
    __PARITY_DICT = {SerialIfaceParityConsts.PARITY_NONE: serial.PARITY_NONE,
                     SerialIfaceParityConsts.PARITY_EVEN: serial.PARITY_EVEN,
                     SerialIfaceParityConsts.PARITY_ODD: serial.PARITY_ODD,
                     SerialIfaceParityConsts.PARITY_MARK: serial.PARITY_MARK,
                     SerialIfaceParityConsts.PARITY_SPACE: serial.PARITY_SPACE}

    def __init__(self, port: str, baud_rate: int, ic_timeout: float, msg_timeout: float,
                 parity: str = SerialIfaceParityConsts.PARITY_NONE, stopbits: int = 1,
                 enqueue_incoming_data: bool = True):
        """
        Class constructor. Initialize serial bus communication:
            Parameters:
                port (str): Serial port
                baud_rate (int):    Bus baud rate
                parity (str): Serial port parity setting
                stopbits (int): Serial port stop bits setting
                ic_timeout (float):  inter-char timeout
                msg_timeout (float): incoming message timeout
                enqueue_incoming_data (bool):  Enqueue incoming data(True case) or not(False case)

        Note: if enqueue_incoming_data is False, new messages will not be stored into the internal queue and can be
        received only using callbacks
        """
        self.__port = port
        self.__baud_rate = baud_rate
        self.__parity = parity
        self.__stopbits = stopbits
        self.__msg_timeout = msg_timeout
        self.__ic_timeout = ic_timeout
        self.__queue = queue.Queue(0) if enqueue_incoming_data else None
        self.__stop_polling_thread = threading.Event()
        self.__clb_list = []
        self.__clb_list_lock = Lock()

        self.__init_bus()

    def __del__(self):
        self.__close_bus()

    def __get_parity_from_string(self, parity_str: str):
        """
        Convert parity string to parity from serial.Serial
            Parameters:
                parity_str (str): raw parity string
            Returns:
                Parity value from serial.Serial
        """
        result = self.__PARITY_DICT.get(parity_str)

        if not result:
            print("Wrong parity value passed: " + parity_str, file=sys.stderr)
            sys.exit(1)

        return result

    def __init_bus(self):
        """
        Initialize serial bus.
        """
        try:
            self.__bus = serial.Serial(self.__port, self.__baud_rate, parity=self.__get_parity_from_string(self.__parity),
                                       stopbits=self.__stopbits,
                                       timeout=self.__msg_timeout, inter_byte_timeout=self.__ic_timeout)
            self.__bus.reset_input_buffer()
            self.__bus.reset_output_buffer()
            self.__pollingThread = threading.Thread(
                target=self.__poll_messages,
                daemon=True
            )
            self.__stop_polling_thread.clear()
            self.__pollingThread.start()

        except serial.SerialException as serialEx:
            print("Failed to initialize Serial Bus: {}".format(serialEx))
            sys.exit(1)
        except Exception as ex:
            print("Failed initialize SerialBus bus_interface: {}".format(ex))
            self.__bus.close()
            sys.exit(1)

    def __close_bus(self):
        """
        Finish polling thread and close serial bus.
        """
        self.__stop_polling_thread.set()
        self.__pollingThread.join()
        try:
            self.__bus.close()
        except Exception as ex:
            print("Failed to close Serial Bus: {}".format(ex))
            sys.exit(1)

    def __poll_messages(self):
        """
            Message polling function
        """
        while not self.__stop_polling_thread.is_set():
            try:
                msg = self.__bus.read(SERIAL_MESSAGE_MAX_BYTES)

                with self.__clb_list_lock:
                    if len(self.__clb_list):
                        for callback in self.__clb_list:
                            callback(msg)
                if self.__queue and len(msg) > 0:
                    self.__queue.put(msg)
            except serial.SerialException as serialEx:
                print("Failed to read message: {}".format(serialEx))
            except queue.Full:
                print("Queue is full. Message lost")

    def send_message(self, msg: bytes):
        """
        Send message to serial interface
            Parameters:
                msg (bytes):    Message to send
            Returns:
                status (bool): True if message has been sent successfully, False otherwise
        """
        try:
            write_bytes = self.__bus.write(msg)
            self.__bus.flush()
        except serial.SerialException as ex:
            print("Failed to send message: {}".format(ex))
            return False
        return write_bytes == len(msg)

    def get_message(self, timeout: float):
        """
        Get message from serial interface
            Parameters:
                timeout (float):  Operation timeout in seconds
            Returns:
                msg (bytes): Received message (None if timeout expired or module works on the mode without data queue)
        """
        if self.__queue is None:
            return None

        try:
            msg = self.__queue.get(block=True, timeout=timeout)
            return msg
        except queue.Empty:
            return None

    def get_parameters(self):
        """
            Get serial interface parameters
                Returns:
                    parameters (dict): Bus parameters
        """
        return {'port': self.__bus.port,
                'baud_rate': self.__bus.baudrate,
                'msg_timeout': self.__bus.timeout,
                'parity': self.__bus.parity,
                'stopbits': self.__bus.stopbits}

    def flush_incoming_data(self):
        """
            Flush incoming data queue
        """
        if self.__queue is None:
            return

        while True:
            try:
                self.__queue.get(block=False)
            except queue.Empty:
                break

    def register_message_callback(self, callback):
        """
            Register incoming message callback
                Parameters:
                    callback (Callable): function to register as callback
        """
        if callback is None:
            print("Callback function is None", file=sys.stderr)
            return
        if callback in self.__clb_list:
            print("Callback function has already registered:" + callback.__name__,  file=sys.stderr)
            return
        with self.__clb_list_lock:
            self.__clb_list.append(callback)

    def unregister_message_callback(self, callback):
        """
            Unregister incoming message callback
                Parameters:
                    callback (Callable): callback function to unregister
        """
        if callback is None:
            print("Callback function is None",  file=sys.stderr)
            return
        if callback not in self.__clb_list:
            print("Callback function is not registered:" + callback.__name__,  file=sys.stderr)
            return
        with self.__clb_list_lock:
            self.__clb_list.remove(callback)

    def clear_callback_list(self):
        """
            Clear list of incoming data callbacks
        """
        with self.__clb_list_lock:
            self.__clb_list.clear()

    def update_port_config(self, baud_rate: int, parity: str, stopbits: int):
        """
            Update configuration of Serial hardware interface
                Parameters:
                    baud_rate (int):    Bus baud rate
                    parity (str): Serial port parity setting
                    stopbits (int): Serial port stop bits setting
        """
        self.__close_bus()

        self.__baud_rate = baud_rate
        self.__parity = parity
        self.__stopbits = stopbits
        self.__init_bus()
