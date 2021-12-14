import allure

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from utils.cli_common_util import CliCommonUtil
from utils.cli_dbus_util import CliDbusUtil
from utils.common.cli_regex_consts import CliRegexConsts


class UsbDriveHelper:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __cli_dbus_util = CliDbusUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None
    assert __cli_dbus_util is not None

    def __init__(self, folder_to_emulate: str, emulated_folder_list: list = None):
        """
        Init helper object.
        :param folder_to_emulate: path where to create folder and emulate the flash. Should be without '/' in the end
        of the string. It is recommended to name the flash drive as sda{XX}. Example: "/run/mmcblk0p4/sda2"
        folder_to_
        :param emulated_folder_list: List of folders to create in the root of the emulated flash.
        """
        self.__flash_drive_path = folder_to_emulate + "/"
        self.__usbstorage_name = folder_to_emulate.split("/")[-1]
        self.__emulated_folder_list = emulated_folder_list

    def emulate_flash_start(self):
        """
        Start emulating the flash drive
        """
        print("emulate_flash_start()")

        with allure.step(f"Start flash emulation for {self.__usbstorage_name}"):
            # create /media/usbstorage/ folder if does not exist
            assert CommonHelper.create_folder(CommonConst.USBSTORAGE_PATH, with_patents=True) is True

            self.__debug_cli.send_message(
                CommonConst.COMMAND_LN_S + self.__flash_drive_path + " " + CommonConst.USBSTORAGE_PATH)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN)

    def emulate_flash_stop(self):
        """
        Stop emulating the flash drive
        """
        print("emulate_flash_stop()")

        with allure.step(f"Stop flash emulation for {self.__usbstorage_name}"):
            CommonHelper.remove_file(CommonConst.USBSTORAGE_PATH + self.__usbstorage_name, forced=True)

    def prepare_emulated_flash_folders(self):
        """
        Prepare folders on emulated flash.
        Creates empty folders in the root path of the emulated flash, including the root folder.
        """
        print("prepare_emulated_flash_folders()")
        self.remove_emulated_flash_folders()

        with allure.step(f"Prepare folders of emulated flash {self.__usbstorage_name}"):
            # create root folder for the flash
            assert CommonHelper.create_folder(self.__flash_drive_path, with_patents=True) is True

            if self.__emulated_folder_list:
                for folder in self.__emulated_folder_list:
                    assert CommonHelper.create_folder(self.__flash_drive_path + folder[1:], with_patents=True) is True

    def remove_emulated_flash_folders(self):
        """
        Prepare folders on emulated flash.
        Removes the root folder of the emulated flash with all the child folders and files.
        """
        print("remove_emulated_flash_folders()")

        with allure.step(f"Remove folders of emulated flash {self.__usbstorage_name}"):
            CommonHelper.remove_file(self.__flash_drive_path, forced=True, recursive=True,
                                     timeout=CommonConst.TIMEOUT_4_MIN)

    def cleanup_emulated_flash_folders(self):
        """
        Removes all files inside the root path and everything inside the registered emulated folders,
        if emulated_folder_list was not None
        """
        print("__cleanup_emulated_usb_drive()")

        with allure.step(f"Cleanup folders of emulated flash {self.__usbstorage_name}"):
            CommonHelper.remove_file(
                self.__flash_drive_path + CommonConst.PREFIX_ALL, forced=True, timeout=CommonConst.TIMEOUT_30_SEC)

            if self.__emulated_folder_list:
                for folder in self.__emulated_folder_list:
                    CommonHelper.remove_file(
                        self.__flash_drive_path + folder[1:] + CommonConst.PREFIX_ALL, forced=True, recursive=True,
                        timeout=CommonConst.TIMEOUT_30_SEC)
