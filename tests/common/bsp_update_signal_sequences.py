class BspUpdateSignalSequences:
    new_fw_available = ["newFirmwareAvailable"]

    new_fw_available_forced = ["forcedFirmwareChecked",
                               "newFirmwareAvailable"]

    new_pckg_available = ["newPackageAvailable"]

    new_pckg_available_forced = ["forcedPackageChecked",
                                 "newPackageAvailable"]

    update_fw_forced = ["forcedFirmwareChecked",
                        "newFirmwareAvailable",
                        "Kernel Update Started",
                        "RootFs Update Started",
                        "Switching To New Firmware"]

    update_package_forced = ["forcedPackageChecked",
                             "newPackageAvailable",
                             "System Backup Started",
                             "System Update Started"]

    update_second_pckg = ["newPackageAvailable",
                          "System Update Started"]

    update_second_pckg_forced = ["forcedPackageChecked",
                                 "newPackageAvailable",
                                 "System Update Started"]

    update_fw_after_resume = ["Kernel Update Started",
                              "RootFs Update Started",
                              "Switching To New Firmware"]

    update_pckg_wo_new_pckg_avail = ["System Backup Started",
                                "System Update Started"]

    update_fw_from_usb_or_after_suspense = ["newFirmwareAvailable",
                                            "Kernel Update Started",
                                            "RootFs Update Started",
                                            "Switching To New Firmware"]

    firmware_check_results = ["firmwareCheckResults"]

    update_pckg_from_usb_or_after_suspense = ["newPackageAvailable",
                                              "System Backup Started",
                                              "System Update Started"]