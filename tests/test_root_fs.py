import re
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.common.root_fs_required_packs import RootFsRequiredPacks
from utils.cli_common_util import CliCommonUtil
from tests.config.config import TEST_BUILD_TYPE


@allure.feature("2.3. Root File System")
@pytest.mark.usefixtures("reboot_and_login", "flush_incoming_data")
class TestRootFileSystem:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.ROOT.010 The Root Filesystem shall include GnuPG")
    def test_system_include_gpg(self):
        with allure.step("Execute below command to check ‘GnuPG’ package exist or not: # type gpg"):
            assert CommonHelper.check_package_presence(CommonConst.COMMAND_PACKAGE_GPG) is True

        with allure.step("Execute below command to print help (gpg --help) of the GnuPG package: # gpg --help"):
            assert CommonHelper.check_package_help(CommonConst.COMMAND_PACKAGE_GPG,
                                                   CommonConst.COMMAND_PACKAGE_GPG_HELP) is True

    @allure.story("SW.BSP.ROOT.020 The Root Filesystem shall include \'diskutils\'")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    def test_system_include_diskutils(self):
        with allure.step("Check ‘disk-utils’ packages exist or not"):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_DISKUTILS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute commands to print help (<util_name> --help) of every disk-utils package."):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_DISKUTILS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True

    @allure.story("SW.BSP.ROOT.030 The Root Filesystem shall include \'ext4utils\'")
    def test_system_include_e2fsprogs(self):
        with allure.step("Check ‘e2fsprogs’ package exist or not"):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_E2FSPROGS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute commands to print help of every e2fsprogs package."):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_E2FSPROGS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True

    @allure.story("SW.BSP.ROOT.040 The Root Filesystem shall include \'DBus\'")
    def test_system_include_libdbus(self):
        with allure.step("Execute command to check ‘DBus’ library exist or not "):
            self.__debug_cli.send_message(CommonConst.COMMAND_FIND_LIBDBUS)
            libs_found_counter = 0
            while self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.FIND_LIBDBUS_RESULT):
                libs_found_counter += 1
            assert libs_found_counter > 0

    @allure.story("SW.BSP.ROOT.050 The Root Filesystem shall include \'procps\'")
    def test_system_include_procps(self):
        with allure.step("Execute command to check 'procps' package exist or not"):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_PROCPS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute command to print help (<util_name> --help) of every procps package."):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_PROCPS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True

    @allure.story("SW.BSP.ROOT.060 The Root Filesystem shall include \'dosfstools\'")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    def test_system_include_dosfstools(self):
        with allure.step("Execute command to check ‘dosfstools’ package exist or not"):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_DOSFSTOOLS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute command to print help of every dosfstools package."):
            for package_data in RootFsRequiredPacks.PACKAGE_LIST_DOSFSTOOLS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True

    @allure.story("SW.BSP.ROOT.070 The root file system shall include at least 1 font with international characters "
                  "support, including CJK support.")
    def test_system_include_fonts(self):
        with allure.step("Execute command to check ‘CJK fonts’ exist or not"):
            font_list = list()
            font_list_lambda = lambda msg: font_list.append(msg)
            self.__debug_cli.register_message_callback(font_list_lambda, CommonRegex.FONT_FORMATS)
            self.__debug_cli.send_message(CommonConst.COMMAND_LS_TRUETYPE)
            time.sleep(CommonConst.TIMEOUT_20_SEC)
            self.__debug_cli.unregister_message_callback(font_list_lambda)
            assert len(font_list)
            for required_font in RootFsRequiredPacks.REQUIRED_FONTS:
                assert any(re.search(re.compile(required_font), font_string) for font_string in font_list)
