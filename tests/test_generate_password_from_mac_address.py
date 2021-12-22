import sys

import allure
import pytest
from time import time
import time

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.config import config as utils_config


@allure.feature("3.1. Authentication Feature")
@pytest.mark.usefixtures("reboot_and_login")
class TestGeneratePasswordFromMacAddress:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @pytest.fixture(scope='class')
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

    def __login_as_root(self, root_password: str):
        print("__login_as_root()")
        self.__cli_common_util.update_login_credentials(user=CommonConst.USER_ROOT, password=root_password)
        self.__recreate_cli_common_util(CommonConst.USER_ROOT, root_password)
        assert self.__cli_common_util.logout() is True
        assert self.__cli_common_util.login() is True
        whoami = self.__whoami()
        assert CommonConst.USER_ROOT in whoami

    def __whoami(self):
        print("__whoami()")
        self.__debug_cli.flush_incoming_data()
        self.__debug_cli.send_message(f"{CommonConst.COMMAND_WHOAMI}")
        whoami = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.USER_NAME)
        assert whoami is not None
        return whoami

    def __current_user_credentials(self):
        current_user_name = utils_config.CLI_COMMON_USER_NAME
        assert current_user_name is not None
        current_user_password = utils_config.CLI_COMMON_PASSWORD
        assert current_user_password is not None
        return current_user_name, current_user_password

    def __recreate_cli_common_util(self, username: str, password: str):
        """
        Create new 'CliCommonUtil' instance to be able to log in as another user.
        :return:
        """
        self.__cli_common_util = CliCommonUtil(self.__debug_cli, login=username, password=password)

    @allure.story("SW.BSP.Authentication.010 Generate password for 'root' user")
    def test_mac_address_extraction_for_root(self):
        assert self.__cli_common_util.login() is True

        with allure.step("Extract MAC Address from the board for 'root' user"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)
            mac_address = self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CommonRegex.WILL_STORE_MAC_DOTTED)
            assert mac_address is not None
            mac_address = CommonRegex.WILL_STORE_MAC_DOTTED.search(mac_address).group(1).strip()

        with allure.step("Generate password from MAC address for user 'root'"):
            root_password = self.__cli_common_util.get_password_from_mac_address(mac_address)
            assert root_password is not None

        with allure.step("Update 'root' credentials"):
            self.__cli_common_util.update_login_credentials(user=CommonConst.USER_ROOT, password=root_password)

        with allure.step("Read current user name and password"):
            updated_user_name, updated_user_password = self.__current_user_credentials()
            assert updated_user_name in CommonConst.USER_ROOT
            assert updated_user_password in root_password
            self.__recreate_cli_common_util(updated_user_name, updated_user_password)

        with allure.step("Log out and log in as 'root'"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_LOGOUT)
            time.sleep(CommonConst.TIMEOUT_10_SEC)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_BOOT)
            time.sleep(CommonConst.TIMEOUT_2_MIN)
            self.__debug_cli.send_message(updated_user_name)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            self.__debug_cli.send_message(updated_user_password)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            whoami = self.__whoami()
            assert CommonConst.USER_ROOT in whoami

    @allure.story("SW.BSP.Authentication.020 Generate password for 'welbilt' user")
    def test_mac_address_extraction_for_welbilt(self):
        assert self.__cli_common_util.login() is True

        with allure.step("Extract MAC Address from the board"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)
            mac_address = self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CommonRegex.WILL_STORE_MAC_DOTTED)
            assert mac_address is not None
            mac_address = CommonRegex.WILL_STORE_MAC_DOTTED.search(mac_address).group(1).strip()

        with allure.step("Generate password from MAC address for user 'welbilt'"):
            welbilt_password = self.__cli_common_util.get_password_from_mac_address(mac_address,
                                                                                    user=CommonConst.USER_WELBILT)
            assert welbilt_password is not None

        with allure.step("Update 'welbilt' credentials"):
            self.__cli_common_util.update_login_credentials(user=CommonConst.USER_WELBILT, password=welbilt_password)

        with allure.step("Read current user name and password"):
            updated_user_name, updated_user_password = self.__current_user_credentials()
            assert updated_user_name in CommonConst.USER_WELBILT
            assert updated_user_password in welbilt_password
            self.__recreate_cli_common_util(updated_user_name, updated_user_password)

        with allure.step("Log out and log in as 'welbilt'"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_LOGOUT)
            time.sleep(CommonConst.TIMEOUT_10_SEC)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_BOOT)
            time.sleep(CommonConst.TIMEOUT_60_SEC)
            self.__debug_cli.send_message(updated_user_name)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            self.__debug_cli.send_message(updated_user_password)
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            whoami = self.__whoami()
            assert CommonConst.USER_WELBILT in whoami
