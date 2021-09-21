"""
The test case has the next requirements:
- NetCAN adapter should be configured and connected to the same LAN, as test Host PC;
- NetCAN adapter should be connected to the Common UI board;
- the related part of comm_support_lib/config/config.py should be configured according
to configuration of NetCAN adapter.
"""
import re
import time

import allure
import pytest

from comm_support_lib.comm_interfaces.can_socket import CAN
from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from utils.cli_common_util import CliCommonUtil
from utils.common.cli_command_consts import CliCommandConsts
from utils.common.cli_regex_consts import CliRegexConsts
from tests.config.config import TEST_BUILD_TYPE


@allure.feature("2.13. CAN")
@pytest.mark.usefixtures("reboot_and_login")
class TestCan:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)
    __can = CAN(CommonConst.CAN_DEFAULT_BAUD)

    assert __debug_cli is not None
    assert __cli_common_util is not None
    assert __can is not None

    __TEST_CASE_10_PARAM_LIST = [
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID_EXTENDED, CommonConst.PARAM_LIST_FIELD_EXTENDED: True,
         CommonConst.PARAM_LIST_FIELD_BAUD: 20000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID, CommonConst.PARAM_LIST_FIELD_EXTENDED: False,
         CommonConst.PARAM_LIST_FIELD_BAUD: 50000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID_EXTENDED, CommonConst.PARAM_LIST_FIELD_EXTENDED: True,
         CommonConst.PARAM_LIST_FIELD_BAUD: 100000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID, CommonConst.PARAM_LIST_FIELD_EXTENDED: False,
         CommonConst.PARAM_LIST_FIELD_BAUD: 125000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID_EXTENDED, CommonConst.PARAM_LIST_FIELD_EXTENDED: True,
         CommonConst.PARAM_LIST_FIELD_BAUD: 250000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID, CommonConst.PARAM_LIST_FIELD_EXTENDED: False,
         CommonConst.PARAM_LIST_FIELD_BAUD: 500000},
        {CommonConst.PARAM_LIST_FIELD_ID: CommonConst.CAN_TEST_ID_EXTENDED, CommonConst.PARAM_LIST_FIELD_EXTENDED: True,
         CommonConst.PARAM_LIST_FIELD_BAUD: 1000000}]

    @pytest.fixture(scope='function', autouse=True)
    def __prepare_test_case(self):
        CommonHelper.configure_can(CommonConst.CAN_INTERFACE, False)

    @allure.story("SW.BSP.CAN.010, SW.BSP.CAN.011 The Linux BSP software shall support SocketCAN communication "
                  "controls and comply with the CAN 2.0 Part A/B standards. (part# TCAN1042VDRQ1)")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    @pytest.mark.parametrize("param_dict", __TEST_CASE_10_PARAM_LIST)
    def test_baud_rates(self, param_dict):
        with allure.step("Setup CAN interface on the board and socket CAN adapter"):
            self.__can.update_iface_config(param_dict.get(CommonConst.PARAM_LIST_FIELD_BAUD))
            self.__can.flush_incoming_data()
            CommonHelper.configure_can(CommonConst.CAN_INTERFACE, True,
                                       param_dict.get(CommonConst.PARAM_LIST_FIELD_BAUD))

        with allure.step("Send bytes from the board to Host PC"):
            assert CommonHelper.perform_cangen(CommonConst.CAN_INTERFACE,
                                               param_dict.get(CommonConst.PARAM_LIST_FIELD_EXTENDED),
                                               bytes(CommonConst.CAN_PAYLOAD),
                                               param_dict.get(CommonConst.PARAM_LIST_FIELD_ID),
                                               CommonConst.CANGEN_DELAY, CommonConst.TIMEOUT_2_SEC) is True

            message: dict = self.__can.get_message(CommonConst.TIMEOUT_5_SEC)
            assert message.get(CAN.INPUT_DATA_FIELD_ID) == param_dict.get(CommonConst.PARAM_LIST_FIELD_ID)
            assert message.get(CAN.INPUT_DATA_FIELD_PAYLOAD) == bytes(CommonConst.CAN_PAYLOAD)

        with allure.step("Send bytes from Host PC to the board"):
            self.__debug_cli.send_message(f"{CommonConst.COMMAND_CANDUMP}{CommonConst.CAN_INTERFACE}")
            # wait some time before continue test. required because it could take some time before candump
            # will be ready to receive a data
            time.sleep(CommonConst.TIMEOUT_2_SEC)

            self.__can.send_message(param_dict.get(CommonConst.PARAM_LIST_FIELD_ID), bytes(CommonConst.CAN_PAYLOAD),
                                    is_extended_id=param_dict.get(CommonConst.PARAM_LIST_FIELD_EXTENDED))
            regex_string = rf"{CommonConst.CAN_INTERFACE}.+" \
                           rf"{hex(param_dict.get(CommonConst.PARAM_LIST_FIELD_ID)).upper().strip('0X')}.+\[" \
                           rf"{len(CommonConst.CAN_PAYLOAD)}\].*{bytes(CommonConst.CAN_PAYLOAD).hex(' ').upper()}"
            result = self.__debug_cli.get_message(CommonConst.TIMEOUT_20_SEC, re.compile(regex_string))

            self.__debug_cli.send_message(CliCommandConsts.COMMAND_CTRL_C)
            self.__debug_cli.get_message(CommonConst.TIMEOUT_10_SEC, CliRegexConsts.REGEX_LOGGED_IN)

            assert result is not None
