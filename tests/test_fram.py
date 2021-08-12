import random
import re

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.23. FRAM")
@pytest.mark.usefixtures("reboot_and_login")
class TestFRAM:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.FRAM.010 The Linux BSP software shall include a driver for FRAM read/write access. "
                  "The FRAM shall have a capacity of at least 32kBytes. (part# FM24V02A-GTR). EEPROM")
    def test_eeprom(self):
        with allure.step("Prepare random integer number"):
            random_number = str(random.randint(CommonConst.TEST_NUMBER_RANGE_MIN, CommonConst.TEST_NUMBER_RANGE_MAX))

        with allure.step("Execute command to write data into eeprom"):
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_ECHO}{random_number} > {CommonConst.EEPROM_FILE}")
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

        with allure.step("Execute command to read back the eeprom content"):
            self.__debug_cli.send_message(CommonConst.COMMAND_HEXDUMP + CommonConst.HEXDUMP_C + CommonConst.EEPROM_FILE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, re.compile(random_number)) is not None

    @allure.story("SW.BSP.FRAM.011 The Linux BSP software shall include a driver for FRAM read/write access. "
                  "The FRAM shall have a capacity of at least 32kBytes. (part# FM24V02A-GTR). FRAM")
    def test_fram(self):
        with allure.step("Prepare random integer number"):
            random_number = str(random.randint(CommonConst.TEST_NUMBER_RANGE_MIN, CommonConst.TEST_NUMBER_RANGE_MAX))

        with allure.step("Execute command to write data into FRAM"):
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_ECHO}{random_number} > {CommonConst.FRAM_FILE}")
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

        with allure.step("Execute command to read back the FRAM content"):
            self.__debug_cli.send_message(CommonConst.COMMAND_HEXDUMP + CommonConst.HEXDUMP_C + CommonConst.FRAM_FILE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, re.compile(random_number)) is not None
