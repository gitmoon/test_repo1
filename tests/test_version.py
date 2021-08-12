import sys
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.20. Version")
@pytest.mark.usefixtures("reboot_and_login")
class TestVersion:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @pytest.fixture(scope='function')
    def __resolve_test_result(self):
        yield
        position = self.__cli_common_util.where_am_i(CommonConst.TIMEOUT_15_MIN)
        if position is self.__cli_common_util.POSITION_UBOOT:
            assert self.__cli_common_util.switch_to_normal_mode() is True
        elif position is self.__cli_common_util.POSITION_LOGIN:
            # do nothing
            pass
        elif position is self.__cli_common_util.POSITION_LOGGED_IN:
            # do nothing
            pass
        else:
            print("Teardown dead end!", file=sys.stderr)
            assert False

    @allure.story("SW.BSP.VERSION.010 The initial hardware release shall indicate a revision of 0 and be incremented "
                  "on each hardware revision. The Linux BSP software shall determine the revision of the hardware upon "
                  "which it is running. The hardware version shall be software accessible without the need for "
                  "board initialization.")
    def test_version(self, __resolve_test_result):
        with allure.step("Check ‘Board ID’ value in U-boot's booting message"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CommonRegex.BOARD_ID_ON_BOOT) is not None
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Switch to bootloader"):
            assert self.__cli_common_util.switch_to_bootloader() is True

        with allure.step("Execute U-boot commands to check device tree file"):
            time.sleep(CommonConst.TIMEOUT_5_SEC)
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_RUN + CommonConst.RUN_FINDFDT)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_UBOOT_CLI) is not None

            self.__debug_cli.send_message(CommonConst.COMMAND_PRINTENV + CommonConst.FDT_FILE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.WB_FDT_FILE) is not None

        with allure.step("Go back to Linux"):
            assert self.__cli_common_util.switch_to_normal_mode() is True
