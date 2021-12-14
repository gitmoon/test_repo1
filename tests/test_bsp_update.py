import random
import re
import sys
import threading
import time
import logging
from builtins import print
from re import Pattern

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.bsp_update_signal_sequences import BspUpdateSignalSequences
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.common.usb_drive_helper import UsbDriveHelper
from tests.config.config import FLASH_DRIVE_PATH, FW_FILE_PATH_ON_FLASH, FW_FILE_PATH_ON_FLASH_CORRUPTED, \
    FW_FILE_PATH_ON_FLASH_MISS_FILE, PACKAGE_FILE_PATH_ON_FLASH, FW_FILE_PATH_ON_FLASH_BAD_KERNEL, \
    FW_FILE_PATH_ON_FLASH_WO_PACKAGES, TEST_BUILD_TYPE
from utils.cli_common_util import CliCommonUtil
from utils.cli_dbus_util import CliDbusUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts
from utils.common.dbus_func_consts import DbusFuncConsts
from utils.common.dbus_signal_consts import DbusSignalConsts

def InitLogger():
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger = logging.getLogger()
    rootLogger.addHandler(consoleHandler)
    rootLogger.setLevel(logging.INFO)
    return rootLogger


@allure.feature("2.26. Firmware Update")
class TestBspUpdate:

    __logger = InitLogger()
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __cli_dbus_util = CliDbusUtil(__debug_cli)
    __polling_thread_stop_event = threading.Event()
    __usb_flash = UsbDriveHelper(FLASH_DRIVE_PATH, [CommonConst.WB_FIRMWARE_USB_PATH, CommonConst.WB_PACKAGE_USB_PATH])
    __polling_thread = None

    assert __debug_cli is not None
    assert __cli_common_util is not None
    assert __cli_dbus_util is not None
    assert __polling_thread_stop_event is not None
    assert __usb_flash is not None

    @staticmethod
    def __compare_result_lists(expected: list[str], real: list[CliDbusUtil.DBusSignalResult]):
        if len(expected) != len(real):
            print("__compare_result_lists() lengths of the lists are not equal", file=sys.stderr)
            return False
        for index in range(0, len(expected), 1):
            if not (expected[index] in real[index].signal or any(
                    expected[index] in signal_result for signal_result in real[index].result_list)):
                print("__compare_result_lists() the lists are not equal", file=sys.stderr)
                return False
        return True

    @classmethod
    def __check_if_signal_need_to_be_skipped(cls, signal_data):
        """
        Check for signal_data is RootFs Update progress, System Backup progress,
        firmwareCheckResults, or packageCheckResults.
        Return True if signal detected, False otherwise.
        For example 'RootFs Update 20%' or 'System Backup 99%'.
        :param signal_data:
        :return:
        """
        for pattern in [CliRegexConsts.ROOT_FS_UPDATE_PROGRESS,
                        CliRegexConsts.SYSTEM_BACKUP_PROGRESS,
                        CliRegexConsts.CHECK_RESULTS_SIGNALS]:
            if re.search(pattern, str(signal_data.result_list)) is not None \
                    or re.search(pattern, str(signal_data.signal)):
                return True
        else:
            return False

    @staticmethod
    def __fw_update_callback(dbus_util: CliDbusUtil, update_state_list: list, stop_event: threading.Event,
                             expected_last_signal: str):
        # clear list before running thread
        update_state_list.clear()

        while not stop_event.is_set():
            signal_data = dbus_util.get_signal()
            if signal_data:
                # Check for Update progress signals.
                # DO NOT include such signals to 'update_state_list'.
                if TestBspUpdate.__check_if_signal_need_to_be_skipped(signal_data):
                    continue

                update_state_list.append(signal_data)
                print("__fw_update_callback() Signal: " + signal_data.signal + "; Result: " + str(
                    signal_data.result_list))
                if expected_last_signal in signal_data.signal or any(
                        expected_last_signal in str(result) for result in signal_data.result_list):
                    print("__fw_update_callback() last signal occurred, stopping thread")
                    return
        print("__fw_update_callback() forced stopped")

    def __prepare_default(self):
        print("__prepare_default()")
        self.__usb_flash.emulate_flash_stop()
        self.__usb_flash.cleanup_emulated_flash_folders()

    def __resolve_test_result(self):
        print("__resolve_test_result()")
        position = self.__cli_common_util.where_am_i(CommonConst.TIMEOUT_15_MIN)
        if position is self.__cli_common_util.POSITION_UBOOT:
            assert self.__cli_common_util.switch_to_normal_mode() is True
            assert self.__cli_common_util.login() is True
        elif position is self.__cli_common_util.POSITION_LOGIN:
            assert self.__cli_common_util.login() is True
        elif position is self.__cli_common_util.POSITION_LOGGED_IN:
            # do nothing
            pass
        else:
            print("Teardown dead end!")
            assert False

    def __teardown_default(self):
        print("__teardown_default()")
        self.__stop_polling_thread()
        self.__cli_dbus_util.clear_subscription_list()
        self.__cli_dbus_util.clear_signal_list()
        self.__resolve_test_result()

    def __start_signal_polling_thread(self, update_state_list, expected_last_signal):
        print("__start_signal_polling_thread()")
        if self.__polling_thread and self.__polling_thread.is_alive():
            self.__polling_thread_stop_event.set()
            self.__polling_thread.join()

        self.__polling_thread_stop_event.clear()
        self.__polling_thread = threading.Thread(
            target=self.__fw_update_callback,
            args=(self.__cli_dbus_util, update_state_list, self.__polling_thread_stop_event, expected_last_signal),
            daemon=True
        )
        self.__polling_thread.start()

    def __wait_for_polling_thread_finish(self, timeout):
        print("__wait_for_polling_thread_finish()")
        if not self.__polling_thread or not self.__polling_thread.is_alive():
            print("__wait_for_polling_thread_finish() no thread alive")
            return True

        self.__polling_thread.join(timeout)
        if not self.__polling_thread.is_alive():
            print("__wait_for_polling_thread_finish() normal finish")
            return True
        else:
            self.__stop_polling_thread()
            print("__wait_for_polling_thread_finish() force finish")
            return False

    def __stop_polling_thread(self):
        print("__stop_polling_thread()")
        if not self.__polling_thread or not self.__polling_thread.is_alive():
            print("__stop_polling_thread() no thread alive")
            return
        self.__polling_thread_stop_event.set()
        self.__polling_thread.join()
        print("__stop_polling_thread() thread is stopped")

    def __get_random_test_version(self):
        print("__get_random_test_version()")
        version = str(random.randint(CommonConst.TEST_VERSION_MIN, CommonConst.TEST_VERSION_MAX))
        print("__get_random_test_version() return " + version)
        return version

    def __modify_fw_version(self, version_string):
        print("__modify_fw_version()")
        self.__debug_cli.send_message(f"{CommonConst.COMMAND_ECHO}{version_string} > {CommonConst.ETC_VERSION}")
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.ETC_VERSION)
        test_version_regex = re.compile(f"^{version_string}$")
        assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, test_version_regex) is not None

    def __get_package_name_using_regex(self, regex):
        print("__get_package_name_using_regex()")
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(CommonConst.COMMAND_LS + CommonConst.PACKAGE_PATH)
        string_with_package_name = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, regex)
        if string_with_package_name:
            return regex.search(string_with_package_name).group(0).strip()
        else:
            return None

    def __set_package_version(self, package_regex: Pattern, version_string):
        print("__set_package_version()")
        package_name = self.__get_package_name_using_regex(package_regex)
        assert package_name is not None
        self.__debug_cli.send_message(
            CommonConst.COMMAND_ECHO + f"{version_string} > {CommonConst.PACKAGE_PATH}{package_name}/{CommonConst.PACKAGE_VERSION_FILE}")
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(
            CommonConst.COMMAND_CAT + f"{CommonConst.PACKAGE_PATH}{package_name}/{CommonConst.PACKAGE_VERSION_FILE}")
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        new_package_version = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, re.compile(version_string))
        assert new_package_version is not None

    def __get_package_version(self, package_regex: Pattern):
        print("__get_package_version()")
        package_name = self.__get_package_name_using_regex(package_regex)
        if package_name is None:
            return None
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(
            CommonConst.COMMAND_CAT + f"{CommonConst.PACKAGE_PATH}{package_name}/{CommonConst.PACKAGE_VERSION_FILE}")
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        package_version_string = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.FW_PCKG_VERSION)
        return CommonRegex.FW_PCKG_VERSION.search(package_version_string).group(0)

    def __update_firmware(self, boot_device: str, fw_path: str, fw_name: str = CommonConst.FW_FILE_NAME):
        print("__update_firmware()")
        update_state_list = []

        self.__resolve_test_result()

        if boot_device == CommonConst.BOOT_DEVICE_SDCARD:
            assert self.__cli_common_util.login() is True
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True
            self.__check_boot_device(CommonConst.BOOT_DEVICE_SDCARD)
        else:
            assert False

        self.__modify_fw_version(self.__get_random_test_version())
        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            self.__stop_polling_thread()
            self.__cli_dbus_util.clear_signal_list()
            assert CommonHelper.copy_file(fw_path + fw_name, CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            self.__cli_dbus_util.clear_subscription_list()
            # wait some time between clearing subscription list and the new subscriptions
            time.sleep(CommonConst.TIMEOUT_10_SEC)
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                       parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + fw_name) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_forced, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None

            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

        self.__cli_dbus_util.clear_subscription_list()

    def __remove_emulated_flash_folders(self):
        print("__remove_emulated_flash_folders()")

        with allure.step("Cleanup both partitions on SD-Card"):
            self.__cli_common_util.reboot()
            self.__cli_common_util.login()
            self.__usb_flash.emulate_flash_stop()

            self.__cli_dbus_util.run_method(DbusFuncConsts.SWITCH_TO_ALT_FW, expected_return=False)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN)

            self.__cli_common_util.login()
            self.__usb_flash.emulate_flash_stop()

        self.__usb_flash.remove_emulated_flash_folders()

    def __check_boot_device(self, desired_device):
        print("__check_boot_device()")
        assert desired_device in self.__cli_dbus_util.run_method(
            DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

    @pytest.fixture(scope='class', autouse=True)
    def __prepare_test_section(self):
        print("__prepare_test_section()")
        assert self.__cli_common_util.login() is True
        self.__usb_flash.prepare_emulated_flash_folders()
        yield
        self.__resolve_test_result()
        assert self.__cli_common_util.reboot() is True
        assert self.__cli_common_util.login() is True
        self.__remove_emulated_flash_folders()

    @pytest.fixture(scope='function')
    def __prepare_for_fw_update(self):
        print("__prepare_for_fw_update()")
        self.__modify_fw_version(self.__get_random_test_version())

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
        print("__run_from_sdcard() after yield")
        self.__teardown_default()

    @pytest.fixture(scope='function')
    def __update_fw_to_restore_partition(self):
        yield
        print("__update_fw_to_restore_partition()")
        self.__update_firmware(CommonConst.BOOT_DEVICE_SDCARD, FW_FILE_PATH_ON_FLASH)

    def __get_fw_info(self, get_alt_fw_version: bool = False):
        print("__get_fw_info()")
        with allure.step("Get current SW version"):
            new_version = self.__cli_dbus_util.run_method(DbusFuncConsts.GET_CURR_SW_VERSION)
        with allure.step("Get current active partition"):
            new_partition = self.__cli_dbus_util.run_method(DbusFuncConsts.GET_CURR_PARTITION)
        if get_alt_fw_version:
            with allure.step("Get alternative SW version"):
                alternate_version = self.__cli_dbus_util.run_method(DbusFuncConsts.GET_ALT_SW_VERSION)
                return new_version, new_partition, alternate_version
        return new_version, new_partition

    def __get_alt_partition(self):
        new_partition = self.__cli_dbus_util.run_method(DbusFuncConsts.GET_CURR_PARTITION)
        if new_partition == 'A':
            return 'B'
        elif new_partition == 'B':
            return 'A'
        else:
            return CommonConst.UNDEFINED


    def __create_model_number_file(self, path: str = CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                   content: str = CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI):
        with allure.step(f"Write {content} to {path}."):
            message_echo = CommonConst.COMMAND_ECHO + content + " > " + \
                path + CommonConst.FILE_MODEL_NUMBER
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(message_echo)
            self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC)

    def __extract_version_from_tar(self, path: str):
        self.__debug_cli.send_message(f"tar -axf {path} {CommonConst.PACKAGE_VERSION_FILE} -O")
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        version = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.FW_PCKG_VERSION)
        version = CommonRegex.FW_PCKG_VERSION.search(version).group(0)
        assert version
        return version

    def __set_fw_version_from_specified_source(self, path: str, version_path: str = CommonConst.ETC_VERSION):
        version = self.__extract_version_from_tar(path=path)
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(f"{CommonConst.COMMAND_ECHO}{version} > {version_path}")
        time.sleep(CommonConst.TIMEOUT_2_SEC)

    @allure.story("SW.BSP.UPDATE.030 Firmware Update through USB Flash on SD Card")
    def test_fw_update_sdcard_from_usb(self, __run_from_sdcard, __prepare_for_fw_update):
        print("test_fw_update_sdcard_from_usb()")
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\""
                " and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            # check "RootFS update progress"
            while True:
                update_progress_message = self.__debug_cli.get_message(
                    CommonConst.TIMEOUT_4_MIN, CliRegexConsts.ROOT_FS_UPDATE_PROGRESS)
                assert update_progress_message is not None
                if CommonConst.ROOTFS_UPDATE_PROGRESS_100 in update_progress_message:
                    break

            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(
                BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Check Linux Kernel version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.PROC_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.LINUX_KERNEL_VERSION) is not None

        with allure.step("Check BSP Release version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BSP_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.BSP_VERSION_RESULT) is not None

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.031 Firmware Update through USB Flash on SD Card, no modelNumber file")
    def test_fw_update_sdcard_from_usb_no_modelNumber_file(self, __run_from_sdcard, __prepare_for_fw_update):
        print("test_fw_update_sdcard_from_usb_no_modelNumber_file()")
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        with allure.step("Delete file 'modelNumber.txt' from /run/media/mmcblk0p4/"):
            print("Check if 'modelNumber.txt' exists under /run/media/mmcblk0p4")
            message_ls = CommonConst.COMMAND_LS + CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FILE_MODEL_NUMBER
            self.__debug_cli.send_message(message_ls)
            received_message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                            CommonRegex.PATH_FILE_NOT_FOUND)
            if received_message is None:
                print("delete file 'modelNumber.txt' from /run/media/mmcblk0p4/")
                assert CommonHelper.remove_file(CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FILE_MODEL_NUMBER) is True

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\""
                " and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(
                BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Check Linux Kernel version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.PROC_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.LINUX_KERNEL_VERSION) is not None

        with allure.step("Check BSP Release version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BSP_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.BSP_VERSION_RESULT) is not None

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.033 Negative: Firmware Update through USB Flash on SD Card, same firmware version")
    def test_fw_update_sdcard_from_usb_same_version(self, __run_from_sdcard):
        print("test_fw_update_sdcard_from_usb_same_version()")

        with allure.step("Set firmware version"):
            self.__set_fw_version_from_specified_source(path=FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME)

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\""
                " and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for 'firmwareCheckResults' signal, should be 'Same Version', update shouldn't start"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SAME_VERSION in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is None

        with allure.step("Emulate USB flash drive unplugging"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.034 Negative: Firmware Update through USB Flash on SD Card, not compatible firmware")
    def test_fw_update_sdcard_from_usb_not_compatible_fw(self, __run_from_sdcard, __prepare_for_fw_update):
        print("test_fw_update_sdcard_from_usb_not_compatible_fw()")

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(content=CommonConst.FILE_MODEL_NUMBER_CONTENT_TEST)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\""
                " and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for 'firmwareCheckResults' signal, should be 'Compatibility Check Failed', update shouldn't start"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is None

        with allure.step("Emulate USB flash drive unplugging"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.040 Firmware Update through USB Flash on SD Card, remove USB Flash after signal newFirmwareAvailable")
    def test_fw_update_sdcard_from_usb_remove_after_detect(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Connect USB flash to Common UI board and wait 3 minutes"):
            self.__usb_flash.emulate_flash_start()
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_fw_available[0] in signal.signal

        with allure.step("Disconnect emulated USB flash from the Common UI board"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Wait until the system will start update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Check Linux Kernel version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.PROC_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.LINUX_KERNEL_VERSION) is not None

        with allure.step("Check BSP Release version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BSP_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.BSP_VERSION_RESULT) is not None

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.041 Negative: Firmware Update through USB Flash on SD Card, remove USB Flash before signal newFirmwareAvailable")
    def test_fw_update_sdcard_from_usb_remove_before_detect(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Connect USB flash to Common UI board"):
            self.__usb_flash.emulate_flash_start()
            time.sleep(CommonConst.TIMEOUT_500_MSEC)

        with allure.step(
                "Do not wait for signal \"newFirmwareAvailable\". Disconnect USB flash from the Common UI board when new firmware is copying to the filesystem"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Wait for some signal from FW update utility"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_60_SEC) is None

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Connect USB flash to Common UI board and wait 4 minutes"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.042 Negative: Firmware Update through USB Flash on SD Card, missing file in the new firmware package")
    def test_fw_update_sdcard_from_usb_image_miss_file(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_MISS_FILE + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\","
                "\"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Connect USB flash to Common UI board"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait until new firmware is copied to the board filesystem"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INCOMPLETE_PACKAGE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is None

        with allure.step("Emulate USB flash drive unplugging"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.043 Firmware Update through USB Flash on SD Card, invalid new firmware package")
    def test_fw_update_sdcard_from_usb_bad_kernel(self, __run_from_sdcard, __prepare_for_fw_update,
                                                  __update_fw_to_restore_partition):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_BAD_KERNEL + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash and wait 3 minutes"):
            self.__usb_flash.emulate_flash_start()
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_fw_available[0] in signal.signal

        with allure.step("Disconnect emulated USB flash from the Common UI board"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Wait until the system will be updated"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and error of Linux kernel magic will be occurred"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN,
                                                CommonRegex.BAD_LINUX_KERNEL) is not None
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_UBOOT_CLI)

        with allure.step("Reset the board from bootloader using the command: reset"):
            self.__debug_cli.send_message(CommonConst.COMMAND_RESET)

        with allure.step("Wait till the board to be rebooted and error of Linux kernel magic will be occurred"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN,
                                                CommonRegex.BAD_LINUX_KERNEL) is not None
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_UBOOT_CLI)

        with allure.step("Reset the board from bootloader using the command: reset"):
            self.__debug_cli.send_message(CommonConst.COMMAND_RESET)

        with allure.step("Wait till the board to be rebooted successfully"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Check Linux Kernel version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.PROC_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.LINUX_KERNEL_VERSION) is not None

        with allure.step("Check BSP Release version"):
            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.BSP_VERSION)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.BSP_VERSION_RESULT) is not None

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version not in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.060 Firmware Update through USB Flash on SD Card, suspend and wait 10 minutes to update")
    def test_fw_update_sdcard_from_usb_with_suspend(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_fw_available[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available, update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after 10 minutes of suspense"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.070 Firmware Update through USB Flash on SD Card, suspend and resume to update")
    def test_fw_update_sdcard_from_usb_with_suspend_and_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_fw_available[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available, update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Resume firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            update_state_list.clear()
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.080 Firmware Update through USB Flash on SD Card, resume to update")
    def test_fw_update_sdcard_from_usb_with_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_fw_available[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available, update_state_list) is True

        with allure.step("Resume firmware update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.090 Firmware Update through USB Flash on SD Card, suspend and reject to update")
    def test_fw_update_sdcard_from_usb_with_suspend_reject(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_fw_available[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available, update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_15_MIN) is None

        with allure.step("Disconnect emulated USB flash from the Common UI board"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the board"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.100 Firmware Update through USB Flash on SD Card, reject to update")
    def test_fw_update_sdcard_from_usb_with_reject(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_fw_available[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Emulate USB flash drive plugging in"):
            self.__usb_flash.emulate_flash_start()

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available, update_state_list) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Disconnect emulated USB flash from the Common UI board"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the board"):
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.111 Negative: Firmware Update from Common UI file system on SD Card, invalid sig file in the new firmware package")
    def test_fw_update_sdcard_from_sdcard_corrupted_image(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.FW_FILE_NAME_INVALID_SIG,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_FW_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME_INVALID_SIG) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INVALID_SIGNATURE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.111.1 Negative: Firmware Update from Common UI file system on SD Card, invalid sig file in the new firmware package (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_corrupted_image(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.FW_FILE_NAME_INVALID_SIG,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME_INVALID_SIG) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INVALID_SIGNATURE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.120 Firmware Update from Common UI file system on SD Card")
    def test_fw_update_sdcard_from_sdcard(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_forced, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.120.1 Firmware Update from Common UI file system on SD Card (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_forced, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.121 Firmware Update from Common UI file system on SD Card, same firmware version")
    def test_fw_update_from_sdcard_same_firmware_version(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        with allure.step("Prepare same firmware version"):
            self.__set_fw_version_from_specified_source(path=FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_forced, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.121.1 Firmware Update from Common UI file system on SD Card, same firmware version (forceUpdate)")
    def test_fw_force_update_from_sdcard_same_firmware_version(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        with allure.step("Prepare same firmware version"):
            self.__set_fw_version_from_specified_source(path=FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_forced, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.123 Negative: Firmware Update from Common UI file system on SD Card, not compatible firmware")
    def test_fw_update_sdcard_not_compatible_firmware(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_TEST)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_FW_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.123.1 Negative: Firmware Update from Common UI file system on SD Card, not compatible firmware (forceUpdate)")
    def test_fw_force_update_sdcard_not_compatible_firmware(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_TEST)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.124 Negative: Firmware Update from Common UI file system on SD Card, broken new firmware package")
    def test_fw_update_sdcard_broken_firmware_package(self, __run_from_sdcard, __prepare_for_fw_update):

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_BROKEN,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_FW_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_BROKEN) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_PACKAGE_BROKEN in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.124.1 Negative: Firmware Update from Common UI file system on SD Card, broken new firmware package (forceUpdate)")
    def test_fw_force_update_sdcard_broken_firmware_package(self, __run_from_sdcard, __prepare_for_fw_update):

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_BROKEN,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_BROKEN) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_PACKAGE_BROKEN in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.130 Switch to alternative firmware on SD Card")
    def test_fw_update_sdcard_switch_to_alternative(self, __run_from_sdcard,
                                                                __prepare_for_fw_update):

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Switch to alternative firmware"):
            self.__cli_dbus_util.run_method(DbusFuncConsts.SWITCH_TO_ALT_FW, expected_return=False)

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.140 Firmware Update from Common UI file system on SD Card, suspend and wait 10 minutes to update")
    def test_fw_update_sdcard_from_sdcard_with_suspend(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after 10 minutes of suspense"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.140.1 Firmware Update from Common UI file system on SD Card, suspend and wait 10 minutes to update (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_with_suspend(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after 10 minutes of suspense"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.150 Firmware Update from Common UI file system on SD Card, suspend and resume to update")
    def test_fw_update_sdcard_from_sdcard_with_suspend_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Resume firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            update_state_list.clear()
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.150.1 Firmware Update from Common UI file system on SD Card, suspend and resume to update (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_with_suspend_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Resume firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            update_state_list.clear()
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.160 Firmware Update from Common UI file system on SD Card, resume to update")
    def test_fw_update_sdcard_from_sdcard_with_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Resume firmware update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story("SW.BSP.UPDATE.160.1 Firmware Update from Common UI file system on SD Card, resume to update (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_with_resume(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Resume firmware update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_fw_after_resume[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_FW_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_fw_after_resume,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version not in old_version
        assert alternate_version in old_version
        assert new_partition not in old_partition

    @allure.story(
        "SW.BSP.UPDATE.170 Firmware Update from Common UI file system on SD Card, suspend and reject to update")
    def test_fw_update_sdcard_from_sdcard_with_suspend_reject(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_TRUE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_15_MIN) is None

        with allure.step("Reboot the board"):
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story(
        "SW.BSP.UPDATE.170.1 Firmware Update from Common UI file system on SD Card, suspend and reject to update (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_with_suspend_reject(self, __run_from_sdcard, __prepare_for_fw_update):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\", \"newFirmwareAvailable\", "
                "\"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_TRUE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_FW_UPDATE) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_15_MIN) is None

        with allure.step("Reboot the board"):
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.180 Firmware Update from Common UI file system on SD Card, reject to update")
    def test_fw_update_sdcard_from_sdcard_with_reject(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_FW_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.180.1 Firmware Update from Common UI file system on SD Card, reject to update (forceUpdate)")
    def test_fw_force_update_sdcard_from_sdcard_with_reject(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_fw_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newFirmwareAvailable\", \"forcedFirmwareChecked\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_FIRMWARE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Execute following command: forceFirmwareUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FW_FILE_NAME) is True

        with allure.step("Wait for firmware to be checked and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_fw_available_forced,
                                               update_state_list) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_FW_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

    @allure.story("SW.BSP.UPDATE.181 Firmware Package Update through USB Flash on SD Card, two new packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_two_new_packs(self, __run_from_sdcard, __update_fw_to_restore_partition):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        self.__update_firmware(CommonConst.BOOT_DEVICE_SDCARD, FW_FILE_PATH_ON_FLASH)

        old_version, old_partition = self.__get_fw_info()

        with allure.step(f"Cleanup   {CommonConst.HW_MANAGER_PACKAGE}"):
            assert CommonHelper.package_remove(CommonConst.HW_MANAGER_PACKAGE) is True

        with allure.step(f"Cleanup   {CommonConst.SCREENGRABBER_PACKAGE}"):
            assert CommonHelper.package_remove(CommonConst.SCREENGRABBER_PACKAGE) is True

        with allure.step("Check version of the packages. They should not be present in the system"):
            assert self.__get_package_version(CommonRegex.RESULT_HW_MANAGER) is None
            assert self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER) is None

        with allure.step("Prepare the packages to update"):
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"packageCheckResults\", "
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True
            # get version of the package
            expected_hw_manager_version = update_state_list[0].result_list[1]

            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__usb_flash.emulate_flash_stop()
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_second_pckg[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg, update_state_list) is True
            # get version of the package
            expected_screengrabber_version = update_state_list[0].result_list[1]

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert expected_hw_manager_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert expected_screengrabber_version in screengrabber_new

    @allure.story("SW.BSP.UPDATE.190 Firmware Package Update through USB Flash on SD Card, one package")
    def test_package_update_sdcard_from_usb_one_package(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Delete file 'modelNumber.txt' from /run/media/mmcblk0p4/"):
            print("Check if 'modelNumber.txt' exists under /run/media/mmcblk0p4")
            message_ls = CommonConst.COMMAND_LS + CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FILE_MODEL_NUMBER
            self.__debug_cli.send_message(message_ls)
            received_message = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                            CommonRegex.PATH_FILE_NOT_FOUND)
            if received_message is None:
                print("delete file 'modelNumber.txt' from /run/media/mmcblk0p4/")
                assert CommonHelper.remove_file(CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.FILE_MODEL_NUMBER) is True

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the package and the board to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])

        with allure.step("Execute commands to listen for signals \"packageCheckResults\","
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)

            # check "System backup progress"
            while True:
                update_progress_message = self.__debug_cli.get_message(
                    CommonConst.TIMEOUT_4_MIN, CliRegexConsts.SYSTEM_BACKUP_PROGRESS)
                assert update_progress_message is not None
                if CommonConst.SYSTEM_BACKUP_UPDATE_PROGRESS_100 in update_progress_message:
                    break

            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert hw_manager_new is not None
            assert package_test_version not in hw_manager_new

    @allure.story("SW.BSP.UPDATE.191 Negative: Firmware Package Update through USB Flash on SD Card, one not compatible package")
    def test_package_update_sdcard_from_usb_one_package_not_compatible_package(self, __run_from_sdcard):

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(content=CommonConst.FILE_MODEL_NUMBER_CONTENT_TEST)

        old_version, old_partition, old_alt_version = self.__get_fw_info(get_alt_fw_version=True)

        with allure.step("Prepare the package and the board to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"packageCheckResults\","
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is None

        with allure.step("Disconnect emulated flash"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_alt_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert hw_manager_new is not None
            assert package_test_version in hw_manager_new

    @allure.story("SW.BSP.UPDATE.192 Negative: Firmware Package Update through USB Flash on SD Card,"
        "two packages, one with the same version")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_two_packages_one_with_same_version(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the packages and the board to update"):
            # set screengrabber version
            screengrabber_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, screengrabber_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            # set hardware manager version
            self.__set_fw_version_from_specified_source(path=PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                                        version_path=CommonConst.HARDWARE_MANAGER_VERSION_PATH)
            package_test_version = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"packageCheckResults\","
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            # wait 'packageCheckResults' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SAME_VERSION in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)

            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__usb_flash.emulate_flash_stop()
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert hw_manager_new is not None
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert screengrabber_new is not None
            assert screengrabber_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.193 Negative: Firmware Package Update through USB Flash on SD Card, two packages, "
        "one package with missing file")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_two_packages_one_with_missing_file(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare the packages and the board to update"):
            # set screengrabber version
            screengrabber_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, screengrabber_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            # set hardware manager version
            package_test_version = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_NO_PACKAGE,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"packageCheckResults\","
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INCOMPLETE_PACKAGE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)

            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__usb_flash.emulate_flash_stop()
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.login() is True
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert hw_manager_new is not None
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert screengrabber_new is not None
            assert screengrabber_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.194 Negative: Firmware Package Update through USB Flash on SD Card after power loss during firmware update")
    def test_package_update_sdcard_from_usb_one_packages_power_loss(self, __run_from_sdcard, __prepare_for_fw_update):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        with allure.step("Prepare the usb storage device and the board for further actions"):
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH + CommonConst.FW_FILE_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH) is True

        old_version, old_partition = self.__get_fw_info()

        with allure.step(
                "Execute commands to listen for signals \"firmwareCheckResults\","
                "\"newFirmwareAvailable\" and \"firmwareUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_FIMWARE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FIRMWARE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()
        with allure.step("Wait for 'firmwareCheckResults', 'firmwareUpdateState' signals"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait for signal 'firmwareUpdateState'
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.KERNEL_UPDATE_STARTED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_FW_UPDATE_STATE)
            assert CommonConst.ROOTFS_UPDATE_STARTED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_FW_UPDATE_STATE)
        with allure.step("Disconnect emulated USB flash from the Common UI board"):
            self.__cli_dbus_util.clear_subscription_list()
            self.__cli_dbus_util.clear_signal_list()
            self.__usb_flash.emulate_flash_stop()
            update_state_list.clear()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        with allure.step("Prepare the packages and the board to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            # copy hw manager package. It can have any version in its name
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        alt_partition = self.__get_alt_partition()
        fw_log = CommonHelper.check_file(alt_partition, CommonConst.CHECK_FW_MANGER_LOG)
        assert new_version in old_version
        assert fw_log is False
        assert new_partition in old_partition

        with allure.step("Delete firmware package from flash drive path to prevent fw update"):
            assert CommonHelper.remove_file(
                FLASH_DRIVE_PATH + CommonConst.WB_FIRMWARE_USB_PATH + CommonConst.FW_FILE_NAME) is True

        with allure.step("Execute commands to listen for signals \"packageCheckResults\","
                         "\"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__usb_flash.emulate_flash_stop()
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Login to Linux"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.login() is True
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True


        with allure.step("Get current boot device"):
            assert CommonConst.BOOT_DEVICE_SDCARD in self.__cli_dbus_util.run_method(
                DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert hw_manager_new is not None
            assert package_test_version not in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.200 Firmware Package Update through USB Flash on SD Card, suspend and wait 10 minutes to update, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_with_suspend_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be available and compare resulted D-Bus signal sequence with required"):
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_pckg_available[0] in signal.signal

        with allure.step("Suspend package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True

        with allure.step("Wait until the system will start update after suspend"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_second_pckg[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.210 Firmware Package Update through USB Flash on SD Card, suspend and resume to update, one package")
    def test_package_update_sdcard_from_usb_with_suspend_resume(self, __run_from_sdcard
                                                                ):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_pckg_available[-1])

        with allure.step("Execute commands to listen for signals \"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Resume firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            update_state_list.clear()
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.220 Firmware Package Update through USB Flash on SD Card, resume to update, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_with_resume_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_pckg_available[0] in signal.signal

        with allure.step("Resume firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_second_pckg[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg, update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.230 Firmware Package Update through USB Flash on SD Card, suspend and reject to update, one package")
    def test_package_update_sdcard_from_usb_with_suspend_reject(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.new_pckg_available[-1])

        with allure.step("Execute commands to listen for signals \"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True

        with allure.step("Reject firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_15_MIN) is None

        with allure.step("Stop emulating the flash drive"):
            self.__usb_flash.emulate_flash_stop()

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.240 Firmware Package Update through USB Flash on SD Card, reject to update, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_usb_with_reject_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          FLASH_DRIVE_PATH + CommonConst.WB_PACKAGE_USB_PATH) is True

        with allure.step("Execute commands to listen for signals \"newPackageAvailable\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Connect emulated flash"):
            self.__usb_flash.emulate_flash_start()
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_pckg_available[0] in signal.signal

        with allure.step("Reject package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True

        with allure.step("Stop emulating the flash drive"):
            signal = self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN)
            assert BspUpdateSignalSequences.new_pckg_available[0] in signal.signal
            self.__usb_flash.emulate_flash_stop()

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.250 Firmware Package Update from Common UI file system on SD Card, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_sdcard_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the system will start update after suspend"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.250.1 Firmware Package Update from Common UI file system on SD Card, two packages (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_from_sdcard_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the system will start update after suspend"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.251 Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one with same version")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_sdcard_two_packs_one_with_same_version(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            self.__set_fw_version_from_specified_source(path=PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                                        version_path=CommonConst.HARDWARE_MANAGER_VERSION_PATH)
            package_test_hardware_manager_version = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            package_test_screengrabber_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_screengrabber_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_hardware_manager_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_screengrabber_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.251.1 Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one with same version (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_from_sdcard_two_packs_one_with_same_version(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            self.__set_fw_version_from_specified_source(path=PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                                        version_path=CommonConst.HARDWARE_MANAGER_VERSION_PATH)
            package_test_hardware_manager_version = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            package_test_screengrabber_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_screengrabber_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_hardware_manager_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_screengrabber_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.252 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one package with invalid sig file")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_two_packs_one_with_invalid_sig_file(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_INVALID_SIG,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_INVALID_SIG) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INVALID_SIGNATURE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.252.1 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one package with invalid sig file (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_two_packs_one_with_invalid_sig_file(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_INVALID_SIG,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_INVALID_SIG) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_INVALID_SIGNATURE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.253 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one package broken")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_two_packages_one_package_broken(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_BROKEN,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_BROKEN) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_PACKAGE_BROKEN in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screen
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.253.1 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one package broken (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_from_two_packages_one_package_broken(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file(path=CommonConst.FW_PCKG_PATH_ON_SDCARD,
                                            content=CommonConst.FILE_MODEL_NUMBER_CONTENT_COMMONUI)

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_BROKEN,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_BROKEN) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_PACKAGE_BROKEN in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screen
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.254 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one not compatible")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_two_packages_one_not_compatible(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_NOT_COMPATIBLE,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_NOT_COMPATIBLE) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.254.1 Negative: Firmware Package Update from Common UI file system on SD Card, "
        "two packages, one not compatible (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_two_packages_one_not_compatible(self, __run_from_sdcard):
        update_state_list = []

        with allure.step("Create 'modelNumber.txt'"):
            self.__create_model_number_file()

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(FW_FILE_PATH_ON_FLASH_CORRUPTED + CommonConst.HW_MANAGER_NAME_NOT_COMPATIBLE,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True

        with allure.step(
                "Execute commands to listen for signals \"packageCheckResults\", \"newPackageAvailable\","
                "\"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_CHECK_RESULTS) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate for hardware manager"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME_NOT_COMPATIBLE) is True
            # wait 'packageCheckResults' signal for harware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_COMPATIBILITY_FAILED in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            # wait 'forcePackageChecked' signal for hardware manager
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.BOOL_FALSE in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_RESULT_BOOL)

        with allure.step("Execute following command: forcePackageUpdate for screengrabber"):
            assert self.__cli_dbus_util.run_method(
                DbusFuncConsts.FORCE_UPDATE,
                parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True
            # wait 'packageCheckResults' signal for screengrabber
            assert self.__cli_dbus_util.get_signal(timeout=CommonConst.TIMEOUT_4_MIN) is not None
            assert CommonConst.CHECK_RESULTS_SUCCESS in self.__debug_cli.get_message(
                CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_DBUS_CHECK_RESULTS)
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.260 Firmware Update from Common UI file system on SD Card, suspend and wait 10 minutes to update, one package")
    def test_package_update_sdcard_from_sdcard_with_suspend(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
        with allure.step("Wait until the system will start update after suspend"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.260.1 Firmware Update from Common UI file system on SD Card, suspend and wait 10 minutes to update, one package (forceUpdate)")
    def test_package_force_update_sdcard_from_sdcard_with_suspend(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend firmware update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
        with allure.step("Wait until the system will start update after suspend"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_from_usb_or_after_suspense,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.270 Firmware Update from Common UI file system on SD Card , suspend and resume to update, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_sdcard_with_suspend_resume_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\" , \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step("Resume package update"):
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.270.1 Firmware Update from Common UI file system on SD Card , suspend and resume to update, two packages (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_from_sdcard_with_suspend_resume_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\" , \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step("Resume package update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_second_pckg_forced[-1])
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_second_pckg_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story("SW.BSP.UPDATE.280 Firmware Update from Common UI file system on SD Card, resume to update, one package")
    def test_package_update_sdcard_from_sdcard_with_resume(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Resume firmware update"):
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new

    @allure.story("SW.BSP.UPDATE.280.1 Firmware Update from Common UI file system on SD Card, resume to update, one package (forceUpdate)")
    def test_package_force_update_sdcard_from_sdcard_with_resume(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Resume firmware update"):
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.RESUME_PACKAGE_UPDATE) is True

        with allure.step("Wait until the system will start update after resume"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_25_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_pckg_wo_new_pckg_avail,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version not in hw_manager_new

    @allure.story(
        "SW.BSP.UPDATE.290 Firmware Update from Common UI file system on SD Card, suspend and reject to update, two packages")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_update_sdcard_from_sdcard_with_suspend_reject_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step("Reject package update"):
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story(
        "SW.BSP.UPDATE.290.1 Firmware Update from Common UI file system on SD Card, suspend and reject to update, two packages (forceUpdate)")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="The test case requires build type \"Development\"")
    def test_package_force_update_sdcard_from_sdcard_with_suspend_reject_two_packs(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            self.__set_package_version(CommonRegex.RESULT_SCREENGRABBER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.SCREENGRABBER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.SCREENGRABBER_NAME) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Suspend package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.SUSPEND_PACKAGE_UPDATE) is True
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step("Reject package update"):
            self.__start_signal_polling_thread(update_state_list, BspUpdateSignalSequences.update_package_forced[-1])
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True

        with allure.step("Wait until the packages will be updated"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.update_package_forced,
                                               update_state_list) is True

        with allure.step("Wait till the board to be rebooted and log in"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        new_version, new_partition, alternate_version = self.__get_fw_info(get_alt_fw_version=True)
        assert new_version in old_version
        assert alternate_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new
            screengrabber_new = self.__get_package_version(CommonRegex.RESULT_SCREENGRABBER)
            assert package_test_version not in screengrabber_new

    @allure.story("SW.BSP.UPDATE.300 Firmware Update from Common UI file system on SD Card, reject to update, one package")
    def test_package_update_sdcard_from_sdcard_with_reject(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_PACKAGE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Reject firmware package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new

    @allure.story("SW.BSP.UPDATE.300.1 Firmware Update from Common UI file system on SD Card, reject to update, one package (forceUpdate)")
    def test_package_force_update_sdcard_from_sdcard_with_reject(self, __run_from_sdcard):
        update_state_list = []

        old_version, old_partition = self.__get_fw_info()

        with allure.step("Prepare package to update"):
            package_test_version = self.__get_random_test_version()
            self.__set_package_version(CommonRegex.RESULT_HW_MANAGER, package_test_version)
            assert CommonHelper.copy_file(PACKAGE_FILE_PATH_ON_FLASH + CommonConst.HW_MANAGER_NAME,
                                          CommonConst.FW_PCKG_PATH_ON_SDCARD) is True
            self.__start_signal_polling_thread(update_state_list,
                                               BspUpdateSignalSequences.new_pckg_available_forced[-1])

        with allure.step(
                "Execute commands to listen for signals \"newPackageAvailable\", \"forcedPackageChecked\" and \"packageUpdateState:\""):
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.NEW_PACKAGE_AVAILABLE) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.FORCED_PACKAGE_CHECKED) is True
            assert self.__cli_dbus_util.subscribe_signal_notification(DbusSignalConsts.PACKAGE_UPDATE_STATE) is True

        with allure.step("Execute following command: forcePackageUpdate"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.FORCE_UPDATE,
                                                   parameter=CommonConst.FW_PCKG_PATH_ON_SDCARD + CommonConst.HW_MANAGER_NAME) is True

        with allure.step(
                "Wait for firmware update to be finished and compare resulted D-Bus signal sequence with required"):
            assert self.__wait_for_polling_thread_finish(CommonConst.TIMEOUT_15_MIN) is True
            assert self.__compare_result_lists(BspUpdateSignalSequences.new_pckg_available_forced,
                                               update_state_list) is True

        with allure.step("Reject firmware package update"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.REJECT_PACKAGE_UPDATE) is True
            assert self.__cli_dbus_util.get_signal(CommonConst.TIMEOUT_10_SEC) is None

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        new_version, new_partition = self.__get_fw_info()
        assert new_version in old_version
        assert new_partition in old_partition

        with allure.step("Check package version"):
            hw_manager_new = self.__get_package_version(CommonRegex.RESULT_HW_MANAGER)
            assert package_test_version in hw_manager_new

    @allure.story("SW.BSP.UPDATE.310 Firmware Update Utility - get firmware update utility version")
    def test_fw_update_sdcard_utility_version(self, __run_from_sdcard):
        with allure.step("Get current firmware update utility version"):
            assert self.__cli_dbus_util.run_method(DbusFuncConsts.GET_SW_VERSION) is not None

    @allure.story("SW.BSP.UPDATE.320 Firmware Update Utility - get current boot device")
    def test_current_boot_device(self, __run_from_sdcard):

        with allure.step("Get current boot device"):
            assert CommonConst.BOOT_DEVICE_SDCARD in self.__cli_dbus_util.run_method(
                DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)

        with allure.step("Reboot the system"):
            self.__cli_dbus_util.clear_subscription_list()
            assert self.__cli_common_util.reboot() is True
            assert self.__cli_common_util.login() is True

        with allure.step("Get current boot device"):
            assert CommonConst.BOOT_DEVICE_SDCARD in self.__cli_dbus_util.run_method(
                DbusFuncConsts.GET_CURRENT_BOOT_DEVICE)
