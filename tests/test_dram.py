import allure
import pytest
import re

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil


@allure.feature("2.4. DRAM")
@pytest.mark.usefixtures("reboot_and_login", "flush_incoming_data")
class TestDram:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.DRAM.020 The Common UI Board shall have at least 128MB_or_256MB DRAM")
    def test_system_have_128mb_or_256mb_dram(self):
        with allure.step("Execute command to check DRAM size"):
            self.__debug_cli.send_message(CommonConst.COMMAND_DRAM_SIZE)
            command_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC,
                                                          CommonRegex.DRAM_SIZE_COMMAND_RESULT)
            dram_size = int(command_result.rstrip('K'))
            assert dram_size >= CommonConst.MIN_DRAM_SIZE, f'DRAM size {dram_size} K ' \
                                                           f'is less than {CommonConst.MIN_DRAM_SIZE} K'
