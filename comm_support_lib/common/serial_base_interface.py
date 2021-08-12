from abc import abstractmethod, ABC


class SerialBaseInterface:
    __metaclass__ = ABC

    @abstractmethod
    def send_message(self, msg):
        pass

    @abstractmethod
    def get_message(self, timeout: float):
        pass

    @abstractmethod
    def register_message_callback(self, callback):
        pass

    @abstractmethod
    def unregister_message_callback(self, callback):
        pass

    @abstractmethod
    def get_parameters(self):
        pass

    @abstractmethod
    def flush_incoming_data(self):
        pass

    @abstractmethod
    def clear_callback_list(self):
        pass

    @abstractmethod
    def update_port_config(self, baud_rate: int, parity: str, stopbits: int):
        pass