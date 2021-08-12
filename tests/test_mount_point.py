import time
import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.cli_dbus_util import CliDbusUtil
from utils.common.cli_regex_consts import CliRegexConsts
from utils.common.dbus_func_consts import DbusFuncConsts
from tests.common.usb_drive_helper import UsbDriveHelper
from tests.config.config import FLASH_DRIVE_PATH


@allure.feature("3.4. Mount point for partition 4")
class TestMountPoint:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __cli_dbus_util = CliDbusUtil(__debug_cli)
    __usb_flash = UsbDriveHelper(FLASH_DRIVE_PATH, [CommonConst.WB_FIRMWARE_USB_PATH, CommonConst.WB_PACKAGE_USB_PATH])

    assert __debug_cli is not None
    assert __cli_common_util is not None

    def __prepare_default(self):
        print("__prepare_default()")
        self.__usb_flash.emulate_flash_stop()
        self.__usb_flash.cleanup_emulated_flash_folders()

    def __check_boot_device(self, desired_device):
        print("__check_boot_device()")
        assert desired_device in self.__cli_dbus_util.run_method(
            DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

    @pytest.fixture(scope='function')
    def __run_from_emmc(self):
        print("__run_from_emmc()")
        CommonHelper.reboot_to_emmc()
        assert self.__cli_common_util.login() is True
        self.__check_boot_device(CommonConst.BOOT_DEVICE_EMMC)
        self.__prepare_default()
        CommonHelper.reboot_to_emmc()
        assert self.__cli_common_util.login() is True
        self.__check_boot_device(CommonConst.BOOT_DEVICE_EMMC)
        yield

    @pytest.fixture(scope='function')
    def __run_from_sdcard(self):
        print("__run_from_sdcard()")
        assert self.__cli_common_util.reboot() is True
        assert self.__cli_common_util.login() is True
        self.__check_boot_device(CommonConst.BOOT_DEVICE_SDCARD)
        self.__prepare_default()
        assert self.__cli_common_util.reboot() is True
        assert self.__cli_common_util.login() is True
        self.__check_boot_device(CommonConst.BOOT_DEVICE_SDCARD)
        yield

    @allure.story("SW.BSP.MountPoint.010 Mount point for emmc should link to '/run/media/mmcblk0p4'")
    def test_mount_point_for_emmc(self, __run_from_emmc):
        with allure.step("Get current boot device"):
            assert CommonConst.BOOT_DEVICE_EMMC in self.__cli_dbus_util.run_method(
                DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

        with allure.step("List '/media/service' directory"):
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_LS}-l {CommonConst.MEDIA_SERVICE}")
            time.sleep(CommonConst.TIMEOUT_2_SEC)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.EMMC_PARTITION_4) is not None

    @allure.story("SW.BSP.MountPoint.020 Mount point for sd-card should link to '/run/media/mmcblk2p4'")
    def test_mount_point_for_sdcard(self, __run_from_sdcard):
        with allure.step("Get current boot device"):
            assert CommonConst.BOOT_DEVICE_SDCARD in self.__cli_dbus_util.run_method(
                DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

        with allure.step("List '/media/service' directory"):
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_LS}-l {CommonConst.MEDIA_SERVICE}")
            time.sleep(CommonConst.TIMEOUT_2_SEC)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.SDCARD_PARTITION_4) is not None