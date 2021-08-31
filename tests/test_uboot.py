"""
To execute test case SW.BSP.UBOOT.010, Common UI Board and the Test PC should be connected using ethernet cable.
Test PC ethernet port should be configured with same IP address as in the tests.config.config.TEST_HOST_IP_ADDR.
Board IP address should be in the same subnet and should be set in the tests.config.config.BOARD_IP_ADDR.
Address tests.config.config.INCORRECT_IP_ADDR should be in another subnet and should not be reachable
To execute test case SW.BSP.UBOOT.060, set tests.config.config.PANEL_ID to 7 for 7-inch board and to 6 for 10-inch board
"""
import sys
import time
import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from tests.config.config import TEST_HOST_IP_ADDR, PANEL_ID, BOARD_IP_ADDR, INCORRECT_IP_ADDR, BOARD_ID
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.27. U-boot Bootloader")
@pytest.mark.usefixtures("flush_incoming_data")
class TestUboot:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @pytest.fixture(scope='class', autouse=True)
    def __switch_to_bootloader(self):
        assert self.__cli_common_util.login() is True
        with allure.step("Stop at U-boot"):
            self.__cli_common_util.switch_to_bootloader()

    @pytest.fixture(scope='class', autouse=True)
    def __switch_to_normal_mode(self):
        yield
        with allure.step("Boot to Linux"):
            self.__cli_common_util.switch_to_normal_mode()

    @pytest.fixture(scope='function')
    def __cleanup_env_variable(self):
        yield
        self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_ENV_DELETE + CommonConst.TEST_ENV_VAR_NAME)
        self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_SAVEENV)
        # It is necessary to have time to execute the command "save"
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_PRINTENV + CommonConst.TEST_ENV_VAR_NAME)
        message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                               CommonRegex.UBOOT_ENV_NOT_DEFINED)
        assert message is not None, f"Unexpected environment variable {CommonConst.TEST_ENV_VAR_NAME} was found"
        print(f"Cleaned up environment variable {CommonConst.TEST_ENV_VAR_NAME} successfully")

    @pytest.fixture(scope='function')
    def __restore_boot_mode(self):
        yield
        self.__cli_common_util.switch_to_normal_mode()
        self.__cli_common_util.login()
        self.__cli_common_util.switch_to_bootloader()

    @allure.story("SW.BSP.UBOOT.010 Verify the U-boot bootloader ethernet commands")
    def test_uboot_ethernet(self):
        with allure.step(f"Ping the Test PC IP address {TEST_HOST_IP_ADDR}"):
            self.__debug_cli.send_message(CommonConst.COMMAND_PING + TEST_HOST_IP_ADDR)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_IP_ADDR_ERROR)
            assert message is not None, "No IP Address error message received"
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_PING_FAILED)
            assert TEST_HOST_IP_ADDR in message, f"Ping IP Address {TEST_HOST_IP_ADDR} did not fail"

        with allure.step(f"Configure the Common UI Board with IP address {BOARD_IP_ADDR}"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_SET_IP_ADDR + BOARD_IP_ADDR)

        with allure.step(f"Ping the Test PC IP address {TEST_HOST_IP_ADDR}"):
            time.sleep(CommonConst.TIMEOUT_2_SEC)  # Wait IP address to apply
            self.__debug_cli.send_message(CommonConst.COMMAND_PING + TEST_HOST_IP_ADDR)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_PING_SUCCESS)
            assert TEST_HOST_IP_ADDR in message, f"Ping IP Address {TEST_HOST_IP_ADDR} failed"

        with allure.step(f"Ping the not existing IP address {INCORRECT_IP_ADDR}"):
            command_start_time = time.time()
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_PING + INCORRECT_IP_ADDR)

            while True:
                if time.time() - command_start_time > CommonConst.TIMEOUT_60_SEC:
                    print("Ping the not existing IP address failed. Timeout occurred", file=sys.stderr)
                    break

                message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                       CommonRegex.UBOOT_PING_FAILED)
                if message:
                    break

            assert INCORRECT_IP_ADDR in message, f"Ping IP Address " \
                                                             f"{INCORRECT_IP_ADDR} did not fail"

    @pytest.mark.parametrize("i2c_dev_name, i2c_dev_id", [("eeprom", CommonConst.I2C_DEV_EEPROM),
                                                          ("fram", CommonConst.I2C_DEV_FRAM)])
    @allure.story("SW.BSP.UBOOT.020, SW.BSP.UBOOT.030 Verify the U-boot bootloader eeprom and fram read/write")
    def test_uboot_eeprom_fram(self, i2c_dev_name, i2c_dev_id):
        with allure.step(f"Set current i2c device to {i2c_dev_name}"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_I2C + CommonConst.COMMAND_UBOOT_DEV + i2c_dev_id)
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_I2C + CommonConst.COMMAND_UBOOT_DEV)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_CURRENT_I2C_DEV)
            current_i2c_dev = int(message.lstrip(CommonConst.CURRENT_I2C_DEV))
            assert current_i2c_dev == int(i2c_dev_id), f"Current I2C bus device {current_i2c_dev} " \
                                                       f"is not {i2c_dev_id}"

        with allure.step(f"Read the data from {i2c_dev_name}"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_I2C + CommonConst.COMMAND_UBOOT_MD)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_I2C_BUS_READ)
            message_list = message.split(" ")

        with allure.step(f"Write the data to the {i2c_dev_name}"):
            data_to_write: str
            if message_list[1] != CommonConst.HEX_AA:
                data_to_write = CommonConst.HEX_AA
            else:
                data_to_write = CommonConst.HEX_BB
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_I2C + CommonConst.COMMAND_UBOOT_MW + data_to_write)

        with allure.step(f"Read the data from {i2c_dev_name}"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_I2C + CommonConst.COMMAND_UBOOT_MD)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_I2C_BUS_READ)
            message_list_new = message.split(" ")
            assert message_list_new[1] == data_to_write, f"Data '{data_to_write}' that was written to {i2c_dev_name} " \
                                                         f"is '{message_list_new[1]}'"
            assert message_list_new[2] == message_list[2], f"Data '{message_list[2]}' on {i2c_dev_name} " \
                                                           f"was accidentally changed to '{message_list_new[2]}'"

    @allure.story("SW.BSP.UBOOT.040, SW.BSP.UBOOT.050 Verify the U-boot bootloader SD Card read/write")
    def test_uboot_sdcard(self, __cleanup_env_variable, __restore_boot_mode):
        with allure.step("Reboot and stop at U-boot"):
            assert self.__cli_common_util.switch_to_bootloader(reboot_command=CliCommandConsts.COMMAND_RESET) is True

    with allure.step("Print the environment variables"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_PRINTENV + CommonConst.TEST_ENV_VAR_NAME)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_ENV_NOT_DEFINED)
            assert message is not None, f"Unexpected environment variable {CommonConst.TEST_ENV_VAR_NAME} was found"

        with allure.step("Create new variable"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_SETENV + CommonConst.TEST_ENV_VAR_NAME + " "
                                          + CommonConst.TEST_ENV_VAR_VALUE)

        with allure.step(f"Save environment variables to SD Card"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_SAVEENV)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_SAVEENV_DONE)
            assert message is not None, "Saving environment variables failed"

        with allure.step("Reboot and stop at U-boot"):
            assert self.__cli_common_util.switch_to_bootloader(reboot_command=CliCommandConsts.COMMAND_RESET) is True

        with allure.step("Print the environment variables"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_PRINTENV + CommonConst.TEST_ENV_VAR_NAME)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_ENV_PRINT_RESULT)
            assert CommonConst.TEST_ENV_VAR_NAME in message, f"Env variable '{CommonConst.TEST_ENV_VAR_NAME}' " \
                                                             f"was not found in message '{message}'"
            assert CommonConst.TEST_ENV_VAR_VALUE in message, f"Env variable value '{CommonConst.TEST_ENV_VAR_VALUE}' " \
                                                              f"was not found in message '{message}'"

        with allure.step(f"Delete the variable '{CommonConst.TEST_ENV_VAR_NAME}'"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_ENV_DELETE + CommonConst.TEST_ENV_VAR_NAME)

        with allure.step(f"Save environment variables to SD Card"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_SAVEENV)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_SAVEENV_DONE)
            assert message is not None, "Saving environment variables failed"

        with allure.step("Reboot and stop at U-boot"):
            assert self.__cli_common_util.switch_to_bootloader(reboot_command=CliCommandConsts.COMMAND_RESET) is True

        with allure.step("Print the environment variables"):
            self.__debug_cli.send_message(CommonConst.COMMAND_UBOOT_PRINTENV + CommonConst.TEST_ENV_VAR_NAME)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                   CommonRegex.UBOOT_ENV_NOT_DEFINED)
            assert message is not None, f"Unexpected environment variable {CommonConst.TEST_ENV_VAR_NAME} was found"

    @allure.story("SW.BSP.UBOOT.060 Verify the U-boot bootloader Board and Panel IDs")
    def test_uboot_board_id_panel_id(self):
        board_id = None
        panel_id = None

        command_start_time = time.time()
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(CliCommandConsts.COMMAND_RESET)

        while True:
            if time.time() - command_start_time > CommonConst.TIMEOUT_60_SEC:
                print("Stop at bootloader failed. Timeout occurred on waiting uboot", file=sys.stderr)
                break

            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)

            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_500_MSEC)

            if message is None:
                continue

            if CliRegexConsts.REGEX_UBOOT_CLI.search(message):
                break

            if CommonRegex.UBOOT_BOARD_ID.search(message):
                board_id = message
                continue

            if CommonRegex.UBOOT_PANEL_ID.search(message):
                panel_id = message
                continue

        with allure.step("Find 'Board ID' in the console terminal output that was printed during the boot process"):
            board_id_int = int(board_id.split('x')[1])
            assert board_id_int == BOARD_ID, f"Board ID {board_id_int} is not {BOARD_ID}"

        with allure.step("Find 'Panel  ID' in the console terminal output that was printed during the boot process"):
            panel_id_int = int(panel_id.split('x')[1])
            assert panel_id_int == PANEL_ID, f"Panel ID {panel_id_int} is not {PANEL_ID}"
