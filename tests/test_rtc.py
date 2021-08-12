import allure
import pytest

from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex


@allure.feature("2.18. Real-Time Clock")
@pytest.mark.usefixtures("reboot_and_login")
class TestRTC:

    @allure.story("SW.BSP.RTC.010 The Linux BSP software shall include a driver for the real-time clock device "
                  "(part# PCF85363ATL/AX).")
    def test_rtc(self):
        with allure.step("Execute below command to check the Linux booting message: dmesg | grep rtc"):
            result = CommonHelper.find_matches(CommonConst.COMMAND_DMESG + CommonConst.DMESG_GREP_RTC,
                                               CommonRegex.DMESG_RESULT_RTC, CommonConst.TIMEOUT_10_SEC)
            assert result is not None and len(result) > 0
