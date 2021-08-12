import allure
import pytest

from comm_support_lib.comm_interfaces.debug_cli import DebugCLI
from tests.common.common_const import CommonConst
from tests.common.common_helper import CommonHelper
from tests.common.common_regex import CommonRegex
from utils.cli_common_util import CliCommonUtil


@allure.feature("2.6. LCD Touch Screen")
@pytest.mark.usefixtures("reboot_and_login")
class TestGraphicsAndVideo:
    __debug_cli = DebugCLI()
    __cli_common_util = CliCommonUtil(__debug_cli)

    assert __debug_cli is not None
    assert __cli_common_util is not None

    @allure.story(
        "SW.BSP.GRAPHICS.030 The Root Filesystem shall include a Qt Framework version of at least 5.6 with the "
        "following support: EGL, OpenGL ES 2.0, QtGraphicalEffects, QtDeclarative, QtSerialport, QtDbus")
    def test_qt_framework(self):
        with allure.step("Check ‘Qt Framework version of at least 5.6’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LIBQT5_ALL_FILES,
                                                 CommonRegex.LIBQT5_ALL_SO_5_6_OR_NEWER,
                                                 CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘EGL’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LIBEGL_ALL_FILES,
                                                 CommonRegex.LIBEGL_ALL_SO, CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘OpenGL ES 2.0’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LIBGLESV2_ALL_FILES,
                                                 CommonRegex.LIBGLESV2_ALL_SO, CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘QtGraphicalEffects’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.GRAPHIC_EFFECTS_PATH,
                                                 CommonRegex.QT_QML_FILES, CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘QtDeclarative’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.USR_LIB_QML_GREP_QML,
                                                 CommonRegex.USR_LIB_QML_FIND_QML, CommonConst.TIMEOUT_30_SEC)) > 0
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.USR_LIB_QML_GREP_QUICK,
                                                 CommonRegex.USR_LIB_QML_FIND_QUICK, CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘QtSerialport’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LIBQT5_GREP_SERIALPORT,
                                                 CommonRegex.LIBQT5_FIND_SERIALPORT, CommonConst.TIMEOUT_30_SEC)) > 0

        with allure.step("Check ‘QtDbus’"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_LS + CommonConst.LIBQT5DBUS_ALL_FILES,
                                                 CommonRegex.LIBQT5DBUS_ALL_SO, CommonConst.TIMEOUT_30_SEC)) > 0

    @allure.story("SW.BSP.GRAPHICS.040 The Root Filesystem shall include 'gstreamer'")
    def test_gstreamer(self):
        with allure.step("Execute command to check if ‘gstreamer’ module exist or not"):
            assert len(CommonHelper.find_matches(CommonConst.COMMAND_FIND + CommonConst.FIND_LIBGSTREAMER,
                                                 CommonRegex.LIBGSTREAMER, CommonConst.TIMEOUT_30_SEC)) > 0
