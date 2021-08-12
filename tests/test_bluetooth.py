import allure
import pytest

from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex


@allure.feature("2.21. Bluetooth")
@pytest.mark.usefixtures("reboot_and_login")
class TestBluetooth:

    @allure.story("SW.BSP.Bluetooth.010 The Linux BSP software shall provide a driver for the WiFi/BT module and "
                  "support the controls for Bluetooth communication and comply with Bluetooth v4.0+LE, or "
                  "later standards. (part# Jorjin WG7833-B0)")
    def test_btwilink(self):
        with allure.step("Execute ‘lsmod’ command to check if “btwilink” driver exists or not"):
            result = CommonHelper.find_matches(CommonConst.COMMAND_LSMOD + CommonConst.LSMOD_GREP_BTWILINK,
                                               CommonRegex.LSMOD_BTWILINK, CommonConst.TIMEOUT_10_SEC)
            assert result is not None and len(result) > 0
