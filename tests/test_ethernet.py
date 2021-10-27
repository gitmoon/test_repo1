"""
The test case has the next requirements:
- the Common UI board should be connected to wired LAN through Ethernet cable;
- the Common UI board should have access to Internet through Ethernet;
- the test Host PC should be accessible for the Common UI board through LAN;
- the Common UI board should be to the same LAN, as the test Host PC;
- the related part of /tests/config/config.py file should be configured according to the
real configuration of the test devices.
"""
import re
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from tests.common.socket_helper import SocketHelper
from tests.config.config import TEST_HOST_IP_ADDR
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts


@allure.feature("2.8. Ethernet")
class TestEthernet:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __socket_helper = SocketHelper()

    __TEST_CASE_60_PARAM_SET = [("10", "half", "off"),
                                ("10", "full", "off"),
                                ("10", "half", "on"),
                                ("10", "full", "on"),
                                ("100", "half", "off"),
                                ("100", "full", "off"),
                                ("100", "half", "on"),
                                ("100", "full", "on")]

    assert __debug_cli is not None
    assert __cli_common_util is not None
    assert __socket_helper is not None

    def __reboot_with_check_mac_read_from_eeprom(self, boot_command):
        read_from_eeprom_found = False
        write_to_emmc_found = False

        self.__debug_cli.flush_incoming_data()

        command_start_time = time.time()
        self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)

        while True:
            if time.time() - command_start_time > CommonConst.TIMEOUT_60_SEC:
                break

            self.__debug_cli.send_message(CliCommandConsts.COMMAND_EMPTY)
            message = self.__debug_cli.get_message(CommonConst.TIMEOUT_500_MSEC)

            if message is None:
                continue

            if CliRegexConsts.REGEX_UBOOT_CLI.search(message):
                break
            if CommonRegex.READ_MAC_EEPROM.search(message):
                read_from_eeprom_found = True
                continue
            if CommonRegex.WILL_STORE_MAC.search(message):
                write_to_emmc_found = True
                continue

        # wait a couple of seconds to ensure that all the empty commands have reached the Common UI board
        # and the system processed them
        time.sleep(CommonConst.TIMEOUT_2_SEC)
        self.__debug_cli.send_message(boot_command)

        assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, CliRegexConsts.REGEX_LOGIN)
        assert self.__cli_common_util.login() is True

        assert read_from_eeprom_found is True
        assert write_to_emmc_found is True

    def __check_mac(self, mac_addr):
        if CommonRegex.MAC_MULTICAST.search(mac_addr) or CommonRegex.MAC_LOCAL.search(mac_addr):
            return False

        if '1' == bin(int(mac_addr.split(" ")[0]))[-1]:
            return False

        return True

    @pytest.fixture(scope='class', autouse=True)
    def __prepare_test_section(self):
        assert self.__cli_common_util.login() is True
        assert self.__cli_common_util.reboot() is True
        assert self.__cli_common_util.login() is True
        CommonHelper.switch_wifi(False)
        # It could take some time to establish network connection
        time.sleep(CommonConst.TIMEOUT_10_SEC)

    @allure.story("SW.BSP.Ethernet.010 The Linux BSP software shall provide a driver for Ethernet communications. "
                  "(part# KSZ8081RNBIA)")
    def test_eth_driver(self):
        with allure.step("Execute command to get a DHCP IP address"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(
                CommonConst.COMMAND_UDHCPC_CHECK + CommonConst.IFACE_ETH + CommonConst.UDHCPC_ARGUMENT_COUNT_30)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.UDHCPC_STARTED) is not None

            lease = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_LEASE_OBTAINED)
            assert lease is not None
            assert CommonRegex.IP_ADDRESS.search(lease).group(0) is not None

            dns_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_ADDING_DNS)
            assert dns_result is not None
            assert CommonRegex.IP_ADDRESS.search(dns_result).group(0) is not None

            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

            time.sleep(CommonConst.TIMEOUT_5_SEC)

            with allure.step("Execute command ‘ping’ to remote host"):
                assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

    @allure.story("SW.BSP.Ethernet.060 - SW.BSP.Ethernet.067 The Linux BSP software shall have the ability to select "
                  "a particular duplex and/or bit rate or to allow them to be selected via the "
                  "auto-negotiation mechanism.")
    @pytest.mark.parametrize("param_set", __TEST_CASE_60_PARAM_SET)
    def test_eth_configurations(self, param_set):
        with allure.step("Execute command to change duplex, bit rate and auto-negotiation params and check them"):
            CommonHelper.perform_ethtool(CommonConst.IFACE_ETH, param_set[0], param_set[1], param_set[2])

        with allure.step("Execute command to check 'ping' between Common UI and Test PC"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

    @allure.story("SW.BSP.Ethernet.070 Verify the MAC address of the board")
    def test_mac_eeprom(self):
        with allure.step("Reboot to U-Boot"):
            assert self.__cli_common_util.switch_to_bootloader() is True

        with allure.step("Read the Common UI Board MAC address from eeprom"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_I2C + CommonConst.I2C_SET_DEV_2)
            self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_UBOOT_CLI)

            self.__debug_cli.send_message(CommonConst.COMMAND_I2C + CommonConst.I2C_READ_MAC_FROM_EEPROM)
            mac_from_eeprom_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.MAC_SEPARATED)

        with allure.step("Boot to Linux and login"):
            assert self.__cli_common_util.switch_to_normal_mode() is True
            assert self.__cli_common_util.login() is True

        with allure.step("Check MAC address from bootloader"):
            assert mac_from_eeprom_result is not None
            mac_addr_string = CommonRegex.MAC_SEPARATED.search(mac_from_eeprom_result).group(0)
            assert self.__check_mac(mac_addr_string) is True

            mac_addr = mac_addr_string.split(" ")

        with allure.step("Read the MAC address from eeprom"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_HEXDUMP + CommonConst.HEXDUMP_READ_MAC_FROM_EEPROM)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, re.compile(
                f"{mac_addr[1]}{mac_addr[0]} {mac_addr[3]}{mac_addr[2]} {mac_addr[5]}{mac_addr[4]}")) is not None

        with allure.step("Read the MAC address using ifconfig"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_IFCONFIG + CommonConst.IFACE_ETH)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, re.compile(
                f"{CommonConst.HWADDR_STRING}{mac_addr[0]}:{mac_addr[1]}:{mac_addr[2]}:"
                f"{mac_addr[3]}:{mac_addr[4]}:{mac_addr[5]}")) is not None

    @allure.story(
        "SW.BSP.Ethernet.090 Boot form SD Card and verify that MAC address of the board is stored on the eMMC")
    def test_mac_sdcard(self):
        with allure.step("Reboot to U-Boot"):
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_REBOOT)

        with allure.step("Login to Linux"):
            assert self.__cli_common_util.login() is True

        with allure.step("Read the MAC address using ifconfig"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_IFCONFIG + CommonConst.IFACE_ETH)
            mac_address_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CommonRegex.IFCONFIG_HWADDR)
            assert mac_address_result is not None
            mac_addr = CommonRegex.MAC_DOTTED.search(mac_address_result).group(0)

        with allure.step("Reboot the Common UI Board and check the console terminal output."):
            self.__reboot_with_check_mac_read_from_eeprom(CliCommandConsts.COMMAND_BOOT)

        with allure.step("Read MAC address from the eMMC"):
            self.__debug_cli.send_message(CommonConst.ETH_MAC)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_60_SEC, re.compile(f"{mac_addr}")) is not None
