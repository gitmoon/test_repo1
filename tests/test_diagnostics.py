import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.config.config import TEST_BUILD_TYPE
from utils.cli_common_util import CliCommonUtil


@allure.feature("2.15. Diagnostics")
@pytest.mark.usefixtures("reboot_and_login")
class TestDiagnostics:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(cli=__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story(
        "SW.BSP.DIAGNOSTICS.010 There shall be controls for on board diagnostics, include bus voltages, temperature "
        "sensing, and LEDs. Voltage")
    def test_voltage_channels(self):
        with allure.step("Check the bus voltages monitor"):
            channel_counter = 0

            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_LS + CommonConst.ALL_VOLTAGE_CHANNELS)
            time.sleep(CommonConst.TIMEOUT_20_SEC)

            while True:
                message = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC,
                                                       CommonRegex.ALL_VOLTAGE_CHANNELS_RESULT)
                if message is None:
                    break
                else:
                    channel_counter += 1
            assert channel_counter == CommonConst.VOLTAGE_CHANNEL_COUNT

    @allure.story(
        "SW.BSP.DIAGNOSTICS.011 There shall be controls for on board diagnostics, include bus voltages, temperature "
        "sensing, and LEDs. Temperature")
    def test_temperature_channels(self):
        with allure.step("Check the temperature sensing of the board"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BOARD_TEMPERATURE_FILE)
            board_temperature = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                             CommonRegex.SYSTEM_TEMPERATURE_VALUE)
            assert board_temperature is not None
            assert int(board_temperature) in CommonConst.SYSTEM_TEMPERATURE_RANGE

        with allure.step("Check the temperature sensing of the CPU"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.CPU_TEMPERATURE_FILE)
            cpu_temperature = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                           CommonRegex.SYSTEM_TEMPERATURE_VALUE)
            assert cpu_temperature is not None
            assert int(cpu_temperature) in CommonConst.SYSTEM_TEMPERATURE_RANGE

    @allure.story("SW.BSP.DIAGNOSTICS.040 The Linux BSP software shall include 'GDB'")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="GDB package available only in \"Development\" builds")
    def test_system_include_gdb(self):
        with allure.step("Execute command to check if 'gdb’ exists or not: # type gdb"):
            assert CommonHelper.check_package_presence(CommonConst.PACKAGE_GDB) is True

        with allure.step("Execute command to check 'gdb' version"):
            assert CommonHelper.check_package_version(CommonConst.PACKAGE_GDB, CommonConst.VERSION_ARGUMENT,
                                                      CommonRegex.GDB_VERSION_RESULT)

        with allure.step("Execute command to check 'gdb' help"):
            assert CommonHelper.check_package_help(CommonConst.PACKAGE_GDB, CommonConst.HELP_ARGUMENT) is True

    @allure.story("SW.BSP.DIAGNOSTICS.050 The Linux BSP software shall include 'Valgrind'")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development",
                        reason="Valgrind package available only in \"Development\" builds")
    def test_system_include_valgrind(self):
        with allure.step("Execute command to check if 'valgrind’ exists or not: # type valgrind"):
            assert CommonHelper.check_package_presence(CommonConst.PACKAGE_VALGRIND) is True

        with allure.step("Execute command to check 'valgrind' version"):
            assert CommonHelper.check_package_version(CommonConst.PACKAGE_VALGRIND, CommonConst.VERSION_ARGUMENT,
                                                      CommonRegex.VALGRIND_VERSION_RESULT)

        with allure.step("Execute command to check 'valgrind' help"):
            assert CommonHelper.check_package_help(CommonConst.PACKAGE_VALGRIND, CommonConst.HELP_ARGUMENT) is True
