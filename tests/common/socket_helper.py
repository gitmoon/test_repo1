import socket
import threading

from tests.common.common_const import CommonConst


class SocketHelper:
    __tcp_server_handle = None
    __udp_server_handle = None
    __tcp_server_event = threading.Event()
    __udp_server_event = threading.Event()

    def __start_server(self, loop_function, host_addr, server_port, stop_event):
        __pollingThread = threading.Thread(
            target=loop_function,
            args=(host_addr, server_port, stop_event),
            daemon=True
        )
        __pollingThread.start()
        return __pollingThread

    @staticmethod
    def __tcp_loop(host_addr: str, server_port: int, stop_event: threading.Event):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.settimeout(CommonConst.TIMEOUT_5_SEC)
            tcp_socket.bind((host_addr, server_port))
            while not stop_event.is_set():
                try:
                    tcp_socket.listen()
                    tcp_connection, addr = tcp_socket.accept()
                except socket.timeout:
                    continue
                with tcp_connection:
                    print('__tcp_loop() connection established with',  addr)
                    while not stop_event.is_set():
                        try:
                            incoming_data = tcp_connection.recv(1024)
                            if not incoming_data:
                                break
                            incoming_data_str = incoming_data.decode("utf-8", "ignore").strip()
                            responce = f"Echo from {host_addr}:{server_port}. Data: {incoming_data_str}"
                            tcp_connection.sendall(responce.encode())
                        except Exception:
                            continue
                print("__tcp_loop() connection has broken")
            print("__tcp_loop() has stopped")

    @staticmethod
    def __udp_loop(host_addr: str, server_port: int, stop_event: threading.Event):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.settimeout(CommonConst.TIMEOUT_5_SEC)
            udp_socket.bind((host_addr, server_port))
            while not stop_event.is_set():
                try:
                    incoming_data, address = udp_socket.recvfrom(1024)

                    if not incoming_data:
                        continue

                    incoming_data_str = incoming_data.decode("utf-8", "ignore").strip()
                    responce = f"Echo from {host_addr}:{server_port}. Data: {incoming_data_str}"
                    udp_socket.sendto(responce.encode(), address)
                except Exception:
                    continue
            print("__udp_loop() has stopped")

    def __stop_server(self, handle, stop_event):
        if not handle:
            return

        if handle.is_alive():
            stop_event.set()
            handle.join()
        else:
            return

    def start_tcp_server(self, host_addr, server_port):
        if self.__tcp_server_handle:
            return
        self.__tcp_server_handle = self.__start_server(self.__tcp_loop, host_addr, server_port, self.__tcp_server_event)

    def stop_tcp_server(self):
        self.__stop_server(self.__tcp_server_handle, self.__tcp_server_event)

    def start_udp_server(self, host_addr, server_port):
        if self.__udp_server_handle:
            return
        self.__udp_server_handle = self.__start_server(self.__udp_loop, host_addr, server_port, self.__udp_server_event)

    def stop_udp_server(self):
        self.__stop_server(self.__udp_server_handle, self.__udp_server_event)