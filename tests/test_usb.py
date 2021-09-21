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
