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

    @allure.story("SW.BSP.DRAM.020 The Common UI Board shall have at least 512MB DRAM")
    def test_system_have_512mb_dram(self):
        with allure.step("Execute command to check DRAM size"):
            self.__debug_cli.send_message(CommonConst.COMMAND_DRAM_SIZE)
            command_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC,
                                                          CommonRegex.DRAM_SIZE_COMMAND_RESULT)
            dram_size = int(command_result.rstrip('K'))
            assert dram_size >= CommonConst.MIN_DRAM_SIZE, f'DRAM size {dram_size} K ' \
                                                           f'is less than {CommonConst.MIN_DRAM_SIZE} K'

    @allure.story("SW.BSP.DRAM.040 The kernel shall reserve at least 64Mbytes of memory for the GPU")
    def test_gpu_have_64mb_memory(self):
        with allure.step("Execute command to check GPU memory size"):
            self.__debug_cli.send_message(CommonConst.COMMAND_GPU_MEM_SIZE)
            command_result = self.__debug_cli.get_message(CommonConst.TIMEOUT_5_SEC,
                                                          CommonRegex.GPU_MEM_SIZE_COMMAND_RESULT)
            gpu_mem_size_list = re.findall(CommonRegex.TOTAL_GPU_MEM_SIZE, command_result)
            gpu_mem_size = int(gpu_mem_size_list[0])
            assert gpu_mem_size >= CommonConst.MIN_GPU_MEM_SIZE, f'GPU memory size {gpu_mem_size} B ' \
                                                                 f'is less than {CommonConst.MIN_GPU_MEM_SIZE} B'
