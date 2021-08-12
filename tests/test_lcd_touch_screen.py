import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil


@allure.feature("2.6. LCD Touch Screen")
@pytest.mark.usefixtures("reboot_and_login")
class TestLcdTouchScreen:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.LCD.020 The Linux LCD display driver shall support 24 bit RGB888 color depth.")
    def test_fbset(self):
        with allure.step("Execute command to check the LCD information"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_FBSET)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.FBSET_RESULT) is not None

    @allure.story("SW.BSP.LCD.040 The Linux LCD backlight driver shall initialize the backlight to on state.")
    def test_backlight(self):
        with allure.step("Check the backlight should be on, and execute command to check backlight power ON/OFF"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BACKLIGHT_POWER_FILE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.BACKLIGHT_POWER_ON) is not None
