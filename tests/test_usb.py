import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.common.usb_required_packs import RequiredPacksForUsb
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_regex_consts import CliRegexConsts
from tests.config.config import TEST_BUILD_TYPE


@allure.feature("2.11. USB")
@pytest.mark.usefixtures("reboot_and_login")
class TestUSB:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.USB.010 There shall be controls to support one USB host port and one USB OTG port.")
    def test_usb_role(self):
        with allure.step("Execute command to check USB host port"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.FILE_USB_HOST_ROLE)
            result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.USB_ROLE)
            assert CommonConst.USB_ROLE_HOST in result

        with allure.step("Check the role of USB OTG and switch it to \"gadget\" if needed"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.FILE_USB_OTG_ROLE)
            result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.USB_ROLE)
            if CommonConst.USB_ROLE_GADGET not in result:
                self.__debug_cli.flush_incoming_data()
                self.__debug_cli.send_message(
                    f"{CommonConst.COMMAND_ECHO} \"{CommonConst.USB_ROLE_GADGET}\" > {CommonConst.FILE_USB_OTG_ROLE}")
                assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                    CliRegexConsts.REGEX_LOGGED_IN) is not None

        with allure.step("Execute command to check USB OTG port"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.FILE_USB_OTG_ROLE)
            result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.USB_ROLE)
            assert CommonConst.USB_ROLE_GADGET in result

    @allure.story("SW.BSP.USB.070 The Linux BSP software shall include 'usbutils'")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    def test_check_usbutils(self):

        with allure.step("Execute commands to check ‘usbutils’ package"):
            for package_data in RequiredPacksForUsb.PACKAGE_LIST:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute commands to print help (<util_name> --help) of every ‘usbutils’ package."):
            for package_data in RequiredPacksForUsb.PACKAGE_LIST:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True
