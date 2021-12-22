"""
The test case has the next requirements:
- the Common UI board should be connected to wired LAN through Ethernet cable;
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
from tests.common.ssh_helper import SshHelper
from tests.config.config import TEST_HOST_IP_ADDR, NETWORKING_TCP_PORT, NETWORKING_UDP_PORT, TEST_BUILD_TYPE
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts
from utils.config.config import CLI_COMMON_USER_NAME, CLI_COMMON_PASSWORD


@allure.feature("2.10. Networking")
@pytest.mark.usefixtures("reboot_and_login")
class TestNetworking:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __socket_helper = SocketHelper()

    assert __debug_cli is not None
    assert __cli_common_util is not None
    assert __socket_helper is not None

    @pytest.fixture(scope='function')
    def __prepare_tcp_server(self):
        with allure.step("Start TCP server on the Test PC:"):
            self.__socket_helper.start_tcp_server(TEST_HOST_IP_ADDR, NETWORKING_TCP_PORT)
        yield
        with allure.step("Stop TCP server on the Test PC:"):
            self.__socket_helper.stop_tcp_server()

    @pytest.fixture(scope='function')
    def __prepare_udp_server(self):
        with allure.step("Start UDP server on the Test PC:"):
            self.__socket_helper.start_udp_server(TEST_HOST_IP_ADDR, NETWORKING_UDP_PORT)
        yield
        with allure.step("Stop UDP server on the Test PC:"):
            self.__socket_helper.stop_udp_server()

    @allure.story("SW.BSP.NETWORK.010 The Linux BSP software shall include an IPv4 protocol stack, "
                  "including IPv4, ICMPv4, TCP and UDP protocols. IPv4, ICMPv4")
    def test_icmpv4(self):
        with allure.step("Execute Ping from Common UI to Test PC"):
            assert CommonHelper.ping(TEST_HOST_IP_ADDR, CommonConst.TIMEOUT_10_SEC) is True

    @allure.story("SW.BSP.NETWORK.011 The Linux BSP software shall include an IPv4 protocol stack, "
                  "including IPv4, ICMPv4, TCP and UDP protocols. TCP")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="GDB package available only in \"Development\" builds")
    def test_tcp(self, __prepare_tcp_server):
        with allure.step("Execute command from Common UI to check TCP connection with Test PC"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_NC}{CommonConst.NC_ARGUMENT_CHECK_TCP_CONNECTION}"
                                          f"{TEST_HOST_IP_ADDR} {NETWORKING_TCP_PORT}")
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.NC_ZV_RESULT) is not None

        with allure.step("Execute command on the Common UI to start TCP session with Test PC:"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_NC}{TEST_HOST_IP_ADDR} {NETWORKING_TCP_PORT}")
            time.sleep(CommonConst.TIMEOUT_2_SEC)
            self.__debug_cli.send_message(CommonConst.TEST_PHRASE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                CommonRegex.RESPONCE_FROM_TCP) is not None

        with allure.step("Close network socket connection"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

    @allure.story("SW.BSP.NETWORK.012 The Linux BSP software shall include an IPv4 protocol stack, including IPv4, "
                  "ICMPv4, TCP and UDP protocols. UDP")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development", reason="GDB package available only in \"Development\" builds")
    def test_udp(self, __prepare_udp_server):
        with allure.step("Execute command on the Common UI to start UDP session with Test PC:"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(
                f"{CommonConst.COMMAND_NC}{CommonConst.NC_ARGUMENT_UDP}{TEST_HOST_IP_ADDR} {NETWORKING_UDP_PORT}")
            time.sleep(CommonConst.TIMEOUT_2_SEC)
            self.__debug_cli.send_message(CommonConst.TEST_PHRASE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                CommonRegex.RESPONCE_FROM_UDP) is not None

        with allure.step("Close network socket connection"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

    @allure.story("SW.BSP.NETWORK.020 The Linux BSP software shall include a DHCPv4 client, and utilize the host IP "
                  "address, the subnet mask, the network broadcast address, default gateway IP addresses, and the DNS "
                  "server IP addresses as provided in a lease received from a DHCP server.")
    @pytest.mark.skipif(TEST_BUILD_TYPE != "Development",
                        reason="The test case requires build type \"Development\"")
    def test_dhcp(self):
        with allure.step("Execute ‘udhcpc’ command to get an IP address, subnet mask, network broadcast address, "
                         "default gateway IP addresses, and the DNS server IP addresses."):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_UDHCPC_CHECK + CommonConst.IFACE_ETH)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.UDHCPC_STARTED) is not None

            lease = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_LEASE_OBTAINED)
            assert lease is not None
            ip_address = CommonRegex.IP_ADDRESS.search(lease).group(0)

            dns_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_ADDING_DNS)
            assert dns_result is not None
            dns_address = CommonRegex.IP_ADDRESS.search(dns_result).group(0)

            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN) is not None

        with allure.step("Check the host IP address, the subnet mask, the network broadcast address"):
            self.__debug_cli.flush_incoming_data()

            self.__debug_cli.send_message(CommonConst.COMMAND_IFCONFIG + CommonConst.IFACE_ETH)
            eth0_params = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                       CommonRegex.IFCONFIG_IP_BCAST_MASK)
            assert eth0_params is not None
            assert ip_address in eth0_params

        with allure.step("Check the default gateway IP addresses"):
            # wait for the default route to be appeared in ip route
            time.sleep(CommonConst.TIMEOUT_5_SEC)

            self.__debug_cli.flush_incoming_data()

            self.__debug_cli.send_message(CommonConst.COMMAND_IP_ROUTE)
            def_route = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                     CommonRegex.IP_ROUTE_DEFAULT_ROUTE)
            assert def_route is not None

        with allure.step("Check the DNS server IP addresses"):
            self.__debug_cli.flush_incoming_data()

            self.__debug_cli.send_message(CommonConst.COMMAND_CAT + CommonConst.RESOLV_CONF_FILE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, re.compile(f"{dns_address}")) is not None

    @allure.story("SW.BSP.NETWORK.030 The Linux BSP software shall include a DNS resolver 'Avahi'")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    def test_avahi_daemon_service(self):
        with allure.step("Check presence of ‘avahi-daemon’ service"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_CHECK_AVAHI_DAEMON_SERVICE)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC,
                                                CommonRegex.AVAHI_DAEMON_SERVICE_RESULT) is not None

    @allure.story("SW.BSP.NETWORK.040 The Linux operating system shall be configured to have an OpenSSH server")
    def test_connect_ssh(self):
        with allure.step("Connect the DUT to an Ethernet network and get a DHCP IP address"):
            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_UDHCPC_CHECK + CommonConst.IFACE_ETH)
            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CommonRegex.UDHCPC_STARTED) is not None

            lease = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, CommonRegex.UDHCPC_LEASE_OBTAINED)
            assert lease is not None
            ip_address = CommonRegex.IP_ADDRESS.search(lease).group(0)

            assert self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC,
                                                CliRegexConsts.REGEX_LOGGED_IN) is not None

            self.__debug_cli.flush_incoming_data()
            self.__debug_cli.send_message(CommonConst.COMMAND_SSHD_SOCKET_START)
            time.sleep(CommonConst.TIMEOUT_5_SEC)

        with allure.step("Execute command to check ssh version"):
            package_ssh = CommonConst.COMMAND_SSH.rstrip()
            assert CommonHelper.check_package_version(package_ssh, CommonConst.SSH_VERSION_ARGUMENT,
                                                      CommonRegex.SSH_VERSION_RESULT) is True

        with allure.step("Execute command to connect and login to DUT from the other PC in the same network"):
            ssh_helper = SshHelper(ip_address, CLI_COMMON_USER_NAME, CLI_COMMON_PASSWORD)
            assert ssh_helper.connect() is True
            ssh_helper.close()

    @allure.story("SW.BSP.NETWORK.050 The Linux BSP software shall include 'networkmanager' and 'iptables'")
    def test_system_include_nm_iptables(self):
        package_nmcli = CommonConst.COMMAND_NMCLI.rstrip()
        package_iptables = CommonConst.COMMAND_IPTABLES.rstrip()
        with allure.step("Execute command to check ‘nmcli’ exist or not"):
            time.sleep(CommonConst.TIMEOUT_5_SEC)
            assert CommonHelper.check_package_presence(package_nmcli) is True

        with allure.step("Execute command to check ‘nmcli’ version"):
            time.sleep(CommonConst.TIMEOUT_5_SEC)
            assert CommonHelper.check_package_version(package_nmcli, CommonConst.VERSION_ARGUMENT,
                                                      CommonRegex.NMCLI_VERSION_RESULT)

        with allure.step("Execute command to check ‘nmcli’ help"):
            assert CommonHelper.check_package_help(package_nmcli, CommonConst.HELP_ARGUMENT) is True

        with allure.step("Execute commands to check ‘iptables’ exist or not"):
            assert CommonHelper.check_package_presence(package_iptables) is True

        with allure.step("Execute command to check ‘iptables’ version"):
            assert CommonHelper.check_package_version(package_iptables, CommonConst.VERSION_ARGUMENT,
                                                      CommonRegex.IPTABLES_VERSION_RESULT)

        with allure.step("Execute command to check ‘iptables’ help"):
            assert CommonHelper.check_package_help(package_iptables, CommonConst.HELP_ARGUMENT) is True
