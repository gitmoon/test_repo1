"""
The test case has the next requirements:
- the related part of /tests/config/config.py file should be configured according to the
real configuration of the test devices.
"""
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.config.config import WIFI_PASS, WIFI_SSID, TEST_HOST_IP_ADDR
from utils.cli_common_util import CliCommonUtil


@allure.feature("2.9. Wi-Fi")
class TestWifi:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    __TEST_CASE_150_PARAM_LIST = [
        (CommonConst.PACKAGE_WPA_SUPPLICANT, "")]

    @pytest.fixture(scope='class', autouse=True)
    def __prepare_test_section(self):
        with allure.step("Reboot the device"):
            assert self.__cli_common_util.login() is True
            assert self.__cli_common_util.reboot() is True
        with allure.step("Login to Linux"):
            assert self.__cli_common_util.login() is True
        with allure.step("Turn off Ethernet connection"):
            CommonHelper.switch_ethernet(False)

    @pytest.fixture(scope='function')
    def __prepare_wifi_connection(self):
        with allure.step("Turn on Wifi connection"):
            CommonHelper.switch_wifi(True)
            CommonHelper.wifi_radio_on()
            # It could take some time to scan wireless network
            time.sleep(CommonConst.TIMEOUT_30_SEC)
            assert CommonHelper.wifi_connect(WIFI_SSID, WIFI_PASS, CommonConst.TIMEOUT_60_SEC) is True

    @pytest.fixture(scope='function')
    def __close_wifi_connection(self):
        yield
        with allure.step("Turn off Wifi connection"):
            CommonHelper.wifi_disconnect(WIFI_SSID)
            CommonHelper.switch_wifi(False)

    @allure.story("SW.BSP.WiFi.010 The Linux BSP software shall include a driver for the Wi Fi radio module "
                  "(part# Jorjin WG7833-B0).")
    def test_ath10k(self):
        with allure.step("Execute ‘lsmod’ command to check if “ath10k” driver exists or not"):
            result = CommonHelper.find_matches(CommonConst.COMMAND_LSMOD + CommonConst.LSMOD_GREP_ATH10K,
                                               CommonRegex.LSMOD_ATH10K, CommonConst.TIMEOUT_10_SEC)
            assert result is not None and len(result) > 0

    @allure.story("SW.BSP.WiFi.023 The Linux Wi-Fi controls shall comply with IEEE 802.11 a/b/g/n standards. "
                  "The Linux Wi-Fi driver shall support operating in infrastructure mode as a client and interoperate "
                  "with the IPv4 protocol stack. Verify wireless connection")
    def test_wifi_connection(self, __prepare_wifi_connection, __close_wifi_connection):
        with allure.step(f"Ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Get an DHCP IPv4 address"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_UDHCPC_CHECK + CommonConst.IFACE_WIFI)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.UDHCPC_STARTED) is not None
            lease = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_LEASE_OBTAINED)
            assert lease is not None
            assert CommonRegex.IP_ADDRESS.search(lease).group(0) is not None

        with allure.step("Get wlan connection information"):
            assert WIFI_SSID in CommonHelper.wifi_check_connection()

    @allure.story(
        "SW.BSP.WiFi.140 The following Wi-Fi parameters shall be software controllable: Verify transmit power")
    def test_tx_power(self, __prepare_wifi_connection, __close_wifi_connection):
        with allure.step("Execute ‘iw’ command to set “transmit power” to 1 dBm"):
            assert CommonHelper.set_wlan_tx_power(CommonConst.IW_POWER_1DBM) is True

        with allure.step("Get the wlan config"):
            search_result = CommonHelper.find_matches(CommonConst.COMMAND_IWCONFIG + CommonConst.COMMAND_WLAN0_INFO,
                                                      CommonRegex.IW_POWER_1DBM, CommonConst.TIMEOUT_10_SEC)
            assert search_result is not None and len(search_result) > 0

        with allure.step(f"Ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Execute ‘iw’ command to set “transmit power” to 15 dBm"):
            assert CommonHelper.set_wlan_tx_power(CommonConst.IW_POWER_15DBM) is True

        with allure.step("Get the wlan config"):
            search_result = CommonHelper.find_matches(CommonConst.COMMAND_IWCONFIG + CommonConst.COMMAND_WLAN0_INFO,
                                                      CommonRegex.IW_POWER_15DBM, CommonConst.TIMEOUT_10_SEC)
            assert search_result is not None and len(search_result) > 0

        with allure.step(f"Ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Execute ‘iw’ command to set “transmit power” to 20 dBm"):
            assert CommonHelper.set_wlan_tx_power(CommonConst.IW_POWER_20DBM) is True

        with allure.step("Get the wlan config"):
            search_result = CommonHelper.find_matches(CommonConst.COMMAND_IWCONFIG + CommonConst.COMMAND_WLAN0_INFO,
                                                      CommonRegex.IW_POWER_20DBM, CommonConst.TIMEOUT_10_SEC)
            assert search_result is not None and len(search_result) > 0

        with allure.step(f"Ping {TEST_HOST_IP_ADDR}"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

        with allure.step("Execute ‘iw’ command to set “transmit power” to auto"):
            assert CommonHelper.set_wlan_tx_power(CommonConst.IW_POWER_AUTO) is True
    #
    # WiFi channels behavior is different on 2,4 and 5GHz. We cannot control Access Point from the test,
    # so this test is not relevant
    # @allure.story("SW.BSP.WiFi.141 The following Wi-Fi parameters shall be software controllable: "
    #               "Verify allowable channels")
    # def test_channels(self, __prepare_wifi_connection, __close_wifi_connection):
    #
    #     with allure.step("Get wlan connection information"):
    #         assert WIFI_SSID in CommonHelper.wifi_check_connection()
    #
    #     with allure.step("Execute ‘iw’ command to set the country code for GB"):
    #         self.__debug_cli.flush_incoming_data()
    #         self.__debug_cli.send_message(
    #             f"{CommonConst.COMMAND_IW}{CommonConst.IW_REG_SET}{CommonConst.WIFI_REGION_GB}")
    #         assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None
    #
    #     with allure.step("Get the country code"):
    #         result = CommonHelper.find_matches(f"{CommonConst.COMMAND_IW}{CommonConst.IW_REG_GET}",
    #                                            CommonRegex.WIFI_COUNTRY_GB, CommonConst.TIMEOUT_10_SEC)
    #         assert result is not None and len(result) > 0
    #
    #     with allure.step("Check allowable channels"):
    #         channels_result = CommonHelper.find_matches(
    #             f"{CommonConst.COMMAND_IWLIST}{CommonConst.IFACE_WIFI} {CommonConst.IWLIST_FREQUENCY}",
    #             CommonRegex.WIFI_CHANNEL_LIST, CommonConst.TIMEOUT_10_SEC)
    #         assert result is not None
    #         for required_channel in WifiChannels.CHANNEL_LIST_GB:
    #             assert any(required_channel in actual_channel for actual_channel in channels_result) is True
    #
    #     with allure.step("Execute ‘iw’ command to set the country code for US"):
    #         self.__debug_cli.flush_incoming_data()
    #         self.__debug_cli.send_message(
    #             f"{CommonConst.COMMAND_IW}{CommonConst.IW_REG_SET}{CommonConst.WIFI_REGION_US}")
    #         assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None
    #
    #     with allure.step("Get the country code"):
    #         result = CommonHelper.find_matches(f"{CommonConst.COMMAND_IW}{CommonConst.IW_REG_GET}",
    #                                            CommonRegex.WIFI_COUNTRY_US, CommonConst.TIMEOUT_10_SEC)
    #         assert result is not None and len(result) > 0
    #
    #     with allure.step("Check allowable channels"):
    #         channels_result = CommonHelper.find_matches(
    #             f"{CommonConst.COMMAND_IWLIST}{CommonConst.IFACE_WIFI} {CommonConst.IWLIST_FREQUENCY}",
    #             CommonRegex.WIFI_CHANNEL_LIST, CommonConst.TIMEOUT_10_SEC)
    #         assert result is not None
    #         for required_channel in WifiChannels.CHANNEL_LIST_US:
    #             assert any(required_channel in actual_channel for actual_channel in channels_result) is True

    @allure.story("SW.BSP.WiFi.150 The Linux BSP software shall include 'wpa-supplicant' and 'wireless-tools'")
    @pytest.mark.parametrize("param_set", __TEST_CASE_150_PARAM_LIST)
    def test_wifi_tools(self, param_set):
        with allure.step("Execute command to check if package exists or not"):
            assert CommonHelper.check_package_presence(param_set[0]) is True

        with allure.step("Execute command to check package help"):
            assert CommonHelper.check_package_help(param_set[0], param_set[1]) is True
