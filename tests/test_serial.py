"""
The test section has the next requirements:
- the Common UI board should be connected with two USB-RS485 converters: one of them should be wired with the board
as for full duplex mode, and the other one should be wired as for half duplex mode;
- the USB-RS485 converters should be connected to the test Host PC and the related part of /tests/config/config.py file
should be configured.
"""
import re
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from comm_support_lib.comm_interfaces.rs_485 import RS485
from comm_support_lib.common.serial_iface_parity_consts import SerialIfaceParityConsts
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.config.config import RS_485_PORT_HALF_DUPLEX
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.12. Serial Ports")
class TestSerial:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __rs485_half_duplex = RS485(RS_485_PORT_HALF_DUPLEX, CommonConst.RS485_DEFAULT_BAUD,
                                SerialIfaceParityConsts.PARITY_NONE, 1)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    __TEST_CASE_70_PARAM_LIST = [300,
                                 1200,
                                 2400,
                                 4800,
                                 9600,
                                 19200,
                                 38400,
                                 57600,
                                 115200,
                                 500000,
                                 1000000]

    def __configure_rs485(self, is_full_duplex: bool, speed: int, rtsonsend: bool, rtsaftersend: bool):
        rtsonsend_state = ""
        rtsaftersend_state = ""

        self.__debug_cli.flush_incoming_data()
        if not rtsonsend:
            rtsonsend_state = "-"
        if not rtsaftersend:
            rtsaftersend_state = "-"

        self.__debug_cli.send_message(
            f"{CommonConst.STTY_F}{CommonConst.TTY_RS485} {CommonConst.STTY_ARGUMENT_SPEED} {str(speed)}")
        assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

    @pytest.fixture(scope='class', autouse=True)
    def __prepare_test_section(self):
        assert self.__cli_common_util.login() is True
        assert self.__cli_common_util.reboot() is True
        assert self.__cli_common_util.login() is True
        self.__debug_cli.flush_incoming_data()

    @allure.story("SW.BSP.SERIAL.010 The Linux BSP software shall provide an UART console serial port driver and "
                  "support a login session for diagnostics and debugging.")
    def test_check_serial_console(self):
        with allure.step("Execute command to check that console working; # date"):
            self.__debug_cli.send_message(CommonConst.COMMAND_DATE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.DATE_RESULT) is not None

    @allure.story("SW.BSP.SERIAL.030 The Linux BSP software shall support single RS-485 serial communication ports. "
                  "(part# MAX13089EASD+T)")
    def test_support_rs485_port(self):
        with allure.step("Execute command: ls /dev/ttyS3"):
            self.__debug_cli.send_message(CommonConst.COMMAND_LS + CommonConst.TTY_RS485)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                re.compile(rf"^{CommonConst.TTY_RS485}")) is not None

    @allure.story("SW.BSP.SERIAL.040 The The RS-485 controls shall be operable as either "
                  "full duplex (four wire) under software control")
    def test_rs485_duplex(self):
        with allure.step("Set RS-485 to half duplex mode"):
            self.__configure_rs485(False, CommonConst.RS485_DEFAULT_BAUD, True, False)

        with allure.step("Execute command: # cat  /dev/ttyS3s"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.TTY_RS485)
            # wait "cat" command to be executed by the system
            time.sleep(CommonConst.TIMEOUT_2_SEC)

        with allure.step("Connect to the RS-485 converter and send test phrase"):
            # as cat command works in echo mode, echo sending causes message corruption in case with long messages
            # to avoid this, CommonConst.TEST_PHRASE_SHORT is used
            self.__rs485_half_duplex.send_message((CommonConst.TEST_PHRASE_SHORT + CommonConst.RS485_EOL).encode())

        with allure.step("Receive the test phrase from the board side"):
            test_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                       re.compile(CommonConst.TEST_PHRASE_SHORT))

        with allure.step("Close cat and check received data"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None
            assert test_result is not None
            assert CommonConst.TEST_PHRASE_SHORT in test_result

        with allure.step("Check send/receive data in half duplex mode"):
            self.__rs485_half_duplex.flush_incoming_data()
            self.__debug_cli.send_message(
                f"{CommonConst.COMMAND_ECHO}{CommonConst.TEST_PHRASE_SHORT} > {CommonConst.TTY_RS485}")
            test_result_bytes: bytes = self.__rs485_half_duplex.get_message(CommonConst.TIMEOUT_10_SEC)
            assert test_result_bytes is not None
            assert CommonConst.TEST_PHRASE_SHORT in test_result_bytes.decode("utf-8", "ignore")

    @allure.story("SW.BSP.SERIAL.070 RS-485 port shall support a maximum baud rate of at least 1Mbps.")
    @pytest.mark.parametrize("baud_rate", __TEST_CASE_70_PARAM_LIST)
    def test_rs485_baud_rate(self, baud_rate):
        with allure.step("Execute command to check if 'setserial' exists or not"):
            self.__configure_rs485(True, baud_rate, True, True)
            self.__rs485_half_duplex.update_serial_config(baud_rate, SerialIfaceParityConsts.PARITY_NONE, 1)

            self.__rs485_half_duplex.flush_incoming_data()
            self.__debug_cli.send_message(
                f"{CommonConst.COMMAND_ECHO}{CommonConst.TEST_PHRASE_SHORT} > {CommonConst.TTY_RS485}")
            test_result_bytes: bytes = self.__rs485_half_duplex.get_message(CommonConst.TIMEOUT_10_SEC)
            assert test_result_bytes is not None
            assert CommonConst.TEST_PHRASE_SHORT in test_result_bytes.decode("utf-8", "ignore")

    @allure.story("SW.BSP.SERIAL.080 The Linux BSP software shall include 'setserial'")
    def test_system_include_setserial(self):
        with allure.step("Execute command to check if 'setserial' exists or not"):
            assert CommonHelper.check_package_presence(CommonConst.PACKAGE_SETSERIAL) is True

        with allure.step("Execute command to check version of setserial app:"):
            assert CommonHelper.check_package_version(CommonConst.PACKAGE_SETSERIAL,
                                                      CommonConst.SETSERIAL_ARGUMENT_VERSION,
                                                      CommonRegex.SETSERIAL_VERSION_RESULT)

        with allure.step("Execute command to check help of setserial app:"):
            assert CommonHelper.check_package_help(CommonConst.PACKAGE_SETSERIAL, CommonConst.HELP_ARGUMENT) is True
