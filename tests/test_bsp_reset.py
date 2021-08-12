"""
Test cases SW.BSP.RESET.020 and SW.BSP.RESET.030 require network connection through Ethernet and Wifi respectively.
Be sure that Ethernet cable is connected and all the necessary parameters has configured in tests/config/config.py file
before running the tests.
"""
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.config.config import TEST_HOST_IP_ADDR, WIFI_SSID, WIFI_PASS
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.7. Reset")
@pytest.mark.usefixtures("reboot_and_login")
class TestBootloaderAndOS:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @pytest.fixture(scope='function', autouse=True)
    def __prepare_test_case(self):
        CommonHelper.switch_wifi(False)
        CommonHelper.switch_ethernet(False)

    @allure.story("SW.BSP.RESET.010 The Linux BSP software shall have the ability to apply a hardware reset "
                  "to the entire controls system.")
    def test_system_hardware_reset(self):
        with allure.step("Prepare test case environment"):
            assert self.__cli_common_util.login() is True

        with allure.step("Execute command: # echo 1 > /proc/sys/kernel/sysrq"):
            self.__debug_cli.send_message(CommonConst.COMMAND_ECHO + CommonConst.SET_SYSRQ)
            time.sleep(CommonConst.TIMEOUT_2_SEC)

        with allure.step("Execute command: # echo b > /proc/sysrq-trigger"):
            self.__debug_cli.send_message(CommonConst.COMMAND_ECHO + CommonConst.SET_SYSRQ_TRIGG)
            time.sleep(CommonConst.TIMEOUT_2_SEC)

        with allure.step("Wait until system reboot"):
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_4_MIN, CliRegexConsts.REGEX_LOGIN) is not None
            assert self.__cli_common_util.login() is True

        with allure.step("Execute command: date"):
            self.__debug_cli.send_message(CommonConst.COMMAND_DATE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC, CommonRegex.DATE_RESULT) is not None

    @allure.story("SW.BSP.RESET.020 The Linux BSP software shall have the ability to apply a hardware reset "
                  "selectively to Ethernet Controls")
    def test_reset_ethernet_iface(self):
        with allure.step("Switch on Ethernet"):
            CommonHelper.switch_ethernet(True)
            # It could take some time to establish network connection
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Execute command: ifconfig eth0 down"):
            CommonHelper.switch_ethernet(False)

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is False

        with allure.step("Execute command: ifconfig eth0 up"):
            CommonHelper.switch_ethernet(True)
            # It could take some time to establish network connection
            time.sleep(CommonConst.TIMEOUT_10_SEC)

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

    @allure.story("SW.BSP.RESET.030 The Linux BSP software shall have the ability to apply a hardware reset "
                  "selectively to Wi-Fi Controls")
    def test_reset_wlan_iface(self):
        with allure.step("Switch on Wifi"):
            CommonHelper.switch_wifi(True)
            CommonHelper.wifi_radio_on()
            # It could take some time to scan wireless network
            time.sleep(CommonConst.TIMEOUT_30_SEC)
            assert CommonHelper.wifi_connect(WIFI_SSID, WIFI_PASS, CommonConst.TIMEOUT_60_SEC) is True

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Execute command: ifconfig wlan0 down"):
            CommonHelper.switch_wifi(False)

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is False

        with allure.step("Execute command: ifconfig wlan0 up"):
            CommonHelper.switch_wifi(True)
            # It could take some time to scan wireless network
            time.sleep(CommonConst.TIMEOUT_30_SEC)
            assert CommonHelper.wifi_connect(WIFI_SSID, WIFI_PASS, CommonConst.TIMEOUT_60_SEC) is True

        with allure.step(f"Execute command: ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

    @allure.story("SW.BSP.RESET.040 Restart device after DIP configuring")
    def test_reboot_after_dip(self):
        with allure.step("Configure Common UI Board to enable page and inquiry scan"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(
                f"{CommonConst.COMMAND_HCICONFIG}{CommonConst.IFACE_HCI0} {CommonConst.IFACE_STATE_UP}")
            self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(
                f"{CommonConst.COMMAND_HCICONFIG}{CommonConst.IFACE_HCI0} {CommonConst.HCICONFIG_PISCAN}")
            self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_HCICONFIG.rstrip())
            self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN)

        with allure.step("Reboot the system"):
            assert self.__cli_common_util.reboot() is True
