from tests.common.common_const import CommonConst


class RequiredPacksForUsb:
    PACKAGE_LIST = [("lsusb", CommonConst.HELP_ARGUMENT),
                    ("lsusb.py", CommonConst.HELP_ARGUMENT),
                    ("usb-devices", CommonConst.HELP_ARGUMENT),
                    ("usbhid-dump", CommonConst.HELP_ARGUMENT)]
