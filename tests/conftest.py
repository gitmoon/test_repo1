import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_helper import CommonHelper
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts

debug_cli = DebugCLI()
cli_common_util = CliCommonUtil(debug_cli)
commonHelper = CommonHelper()

assert debug_cli is not None
assert cli_common_util is not None


@pytest.fixture(scope='class')
def reboot():
    assert cli_common_util.login() is True
    with allure.step("Reboot the device"):
        assert cli_common_util.reboot() is True


@pytest.fixture(scope='class')
def reboot_and_login():
    with allure.step("Reboot the device"):
        assert cli_common_util.login() is True
        assert cli_common_util.reboot() is True
    with allure.step("Login to Linux"):
        assert cli_common_util.login() is True


@pytest.fixture(scope='function')
def reboot_to_emmc():
    assert cli_common_util.login() is True
    with allure.step("Reboot the device and boot from eMMC"):
        assert cli_common_util.reboot_to(boot_device=cli_common_util.BOOT_DEVICE_EMMC) is True


@pytest.fixture(scope='class')
def reboot_after_finish():
    yield
    with allure.step("Reboot the device after finish test section"):
        assert cli_common_util.reboot() is True


@pytest.fixture(scope='function')
def login_to_linux():
    with allure.step("Login to Linux"):
        assert cli_common_util.login() is True


@pytest.fixture(scope='function')
def flush_incoming_data():
    debug_cli.flush_incoming_data()


@pytest.fixture(scope='function')
def switch_to_bootloader():
    assert cli_common_util.login() is True
    with allure.step("Reboot and stop at U-boot"):
        cli_common_util.switch_to_bootloader()


@pytest.fixture(scope='function')
def switch_to_emmc_bootloader():
    assert cli_common_util.login() is True
    with allure.step("Reboot and stop at U-boot"):
        cli_common_util.switch_to_bootloader()
    with allure.step("Reset to eMMC U-boot"):
        cli_common_util.switch_to_bootloader(reboot_command=CliCommandConsts.COMMAND_BOOT_FROM_EMMC)


@pytest.fixture(scope='function')
def switch_to_normal_mode():
    yield
    with allure.step("Boot to Linux"):
        cli_common_util.switch_to_normal_mode()
