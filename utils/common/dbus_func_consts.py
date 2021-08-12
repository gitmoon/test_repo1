class DbusFuncConsts:
    # Common consts
    FORCE_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.forceUpdate"
    # F/W consts
    GET_CURR_PARTITION: str = "org.welbilt.firmwaremanager.FirmwareInterface.getCurrentPartition"
    GET_CURR_SW_VERSION: str = "org.welbilt.firmwaremanager.FirmwareInterface.getCurrentSWversion"
    GET_ALT_SW_VERSION: str = "org.welbilt.firmwaremanager.FirmwareInterface.getAltSWversion"
    SUSPEND_FW_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.suspendFirmwareUpdate"
    RESUME_FW_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.resumeFirmwareUpdate"
    REJECT_FW_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.rejectFirmwareUpdate"
    FORCE_FW_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.forceFirmwareUpdate"
    SWITCH_TO_ALT_FW: str = "org.welbilt.firmwaremanager.FirmwareInterface.switchToAltFirmware"
    # package consts
    SUSPEND_PACKAGE_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.suspendPackageUpdate"
    RESUME_PACKAGE_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.resumePackageUpdate"
    REJECT_PACKAGE_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.rejectPackageUpdate"
    FORCE_PACKAGE_UPDATE: str = "org.welbilt.firmwaremanager.FirmwareInterface.forcePackageUpdate"
    # additional consts
    GET_SW_VERSION: str = "org.welbilt.firmwaremanager.FirmwareInterface.getSwVersion"
    GET_CURRENT_BOOT_DEVICE: str = "org.welbilt.firmwaremanager.FirmwareInterface.getCurrentBootDev"
