# Debug CLI config

# Port of the USB-UART serial adapter
DEBUG_CLI_SERIAL_PORT = "COM9"
# Baud rate of the USB-UART serial adapter, on which it should work
DEBUG_CLI_SERIAL_BAUD = 115200
# Inter-character timeout. Helps to avoid inter-frame gaps
DEBUG_CLI_INTERCHAR_TIMEOUT = 0.5
# Incoming message receiving timeout.
DEBUG_CLI_MSG_TIMEOUT = 3

# CAN config
# currently supports only SocketCAN implementation

# Socket address including host IP-address amd port of the SocketCAN adapter
CAN_SOCKET = "socket://192.168.0.1:1234"
# Incoming message receiving timeout. Helps to avoid inter-frame gaps
CAN_MSG_TIMEOUT = 10

# RS-485 config

# Inter-character timeout. Helps to avoid inter-frame gaps
RS_485_INTERCHAR_TIMEOUT = 0.1
# Incoming message receiving timeout.
RS_485_MSG_TIMEOUT = 5