import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts

@allure.feature("2.2. Boot Loader and Operating System")
@pytest.mark.usefixtures("login_to_linux")
class TestBootloaderAndOS:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.OS.030 The software shall include a U-Boot boot loader and a Linux operating system.")
    def test_system_support_uboot_and_linux_os(self):
        with allure.step("Reboot the Common UI Board"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)
            command_start_time = time.time()
            self.__debug_cli.flush_incoming_data()

        with allure.step("Push empty command to the terminal"):
            while True:
                if time.time() - command_start_time > CommonConst.TIMEOUT_4_MIN:
                    assert False
                self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
                if self.__debug_cli.get_message(CommonConst.TIMEOUT_500_MSEC, CliRegexConsts.REGEX_UBOOT_CLI):
                    break

        with allure.step("Check the console terminal output, there should be U-boot prompt \"=>\" shown on the window"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CliRegexConsts.REGEX_UBOOT_CLI) is not None

        with allure.step("Execute below command to boot up the system into Linux environment: # boot"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_BOOT)

        with allure.step("Check the console terminal output"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGIN) is not None
            self.__cli_common_util.wait_for_links_ready_after_start()

        with allure.step("Type login: root, password: welbiltUser!2227 to login"):
            assert self.__cli_common_util.login() is True

    @allure.story("SW.BSP.OS.080 The Linux BSP software shall include a Linux kernel version of at least 4.4.43.")
    def test_check_linux_kernel_version(self):
        with allure.step("Check the version of the Linux by executing below command: # uname -r"):
            self.__debug_cli.send_message(CommonConst.COMMAND_KERNEL_VERSION)
            kernel_version_str: str = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC,
                                                                   CommonRegex.LINUX_KERNEL_VERSION)
            assert kernel_version_str is not None
            version_array = [int(element) for element in kernel_version_str.split("-")[0].split(".")]
            assert len(version_array) == 3
            current_version = version_array[2] + version_array[1] * 100 + version_array[0] * 1000
            assert current_version >= CommonConst.MINIMAL_KERNEL_VERSION

    @allure.story("SW.BSP.OS.100 The Linux operating system shall support a software-initiated shutdown and "
                  "restart of the Linux operating system and its system services.")
    def test_system_software_restart(self):
        with allure.step("Execute below command to reboot the device: # reboot"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGIN) is not None
            self.__cli_common_util.wait_for_links_ready_after_start()
