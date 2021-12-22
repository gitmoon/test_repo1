import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.audio_required_packs import RequiredPacksForAudio
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil
from tests.config.config import TEST_BUILD_TYPE


@allure.feature("2.17. Audio")
@pytest.mark.usefixtures("reboot_and_login")
class TestAudio:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story("SW.BSP.AUDIO.010 The Linux BSP software shall include drivers for the audio amplifier "
                  "(part# TAS5720MDCAR).")
    def test_tas(self):
        with allure.step("Execute below command to check audio amplifier driver: dmesg | grep tas5720-audio"):
            result = CommonHelper.find_matches(CommonConst.COMMAND_DMESG + CommonConst.DMESG_GREP_TAS_AUDIO,
                                               CommonRegex.DMESG_RESULT_TAS_AUDIO, CommonConst.TIMEOUT_10_SEC)
            assert result is not None and len(result) > 0

    @allure.story("SW.BSP.AUDIO.050 The Linux BSP software shall include ALSA and the following ALSA "
                  "support libraries: a) alsalib; b) alsa-plugins; c) alsa-tools; d) alsa-utils")
    @pytest.mark.skipif(TEST_BUILD_TYPE == "Slim",
                        reason="The test case requires build type \"Production\" or \"Development\"")
    def test_check_alsa(self):

        with allure.step("Execute command to check if ALSA libraries exist or not"):
            result = CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LS_ALSA_LIB_ALL,
                                               CommonRegex.LS_ALSA_LIB_RESULT, CommonConst.TIMEOUT_10_SEC)
            assert result is not None and len(result) > 0

        with allure.step("Execute command to check if ‘alsa-plugins’ exist or not "):
            result = CommonHelper.find_matches(CommonConst.COMMAND_FIND + CommonConst.FIND_ALSA_MODULES_ALL,
                                               CommonRegex.FIND_ALSA_MODULES_RESULT, CommonConst.TIMEOUT_20_SEC)
            assert result is not None and len(result) > 0

        with allure.step("Execute commands to check if ‘alsa-tools’ exist or not"):
            for package_data in RequiredPacksForAudio.PACKAGE_LIST_ALSA_TOOLS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute commands to print help (<util_name> --help) of every ‘alsa-tools’ package."):
            for package_data in RequiredPacksForAudio.PACKAGE_LIST_ALSA_TOOLS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True

        with allure.step("Execute commands to check if ‘alsa-utils’ exist or not"):
            for package_data in RequiredPacksForAudio.PACKAGE_LIST_ALSA_UTILS:
                assert CommonHelper.check_package_presence(package_data[0]) is True

        with allure.step("Execute commands to print help (<util_name> --help) of every ‘alsa-utils’ package."):
            for package_data in RequiredPacksForAudio.PACKAGE_LIST_ALSA_UTILS:
                assert CommonHelper.check_package_help(package_data[0], package_data[1]) is True
