from tests.common.common_const import CommonConst


class RequiredPacksForAudio:
    PACKAGE_LIST_ALSA_UTILS = [("alsactl", CommonConst.HELP_ARGUMENT),
                               ("amixer", CommonConst.HELP_ARGUMENT),
                               ("alsamixer", CommonConst.HELP_ARGUMENT),
                               ("aplay", CommonConst.HELP_ARGUMENT),
                               ("arecord", CommonConst.HELP_ARGUMENT)]

    PACKAGE_LIST_ALSA_TOOLS = [("as10k1", CommonConst.HELP_ARGUMENT),
                               ("cspctl", CommonConst.HELP_ARGUMENT),
                               ("hda-verb", CommonConst.HELP_ARGUMENT),
                               ("hdajacksensetest", CommonConst.HELP_ARGUMENT),
                               ("mixartloader", CommonConst.HELP_ARGUMENT),
                               ("pcxhrloader", CommonConst.HELP_ARGUMENT),
                               ("sbiload", CommonConst.HELP_ARGUMENT),
                               ("sscape_ctl", CommonConst.HELP_ARGUMENT),
                               ("us428control", CommonConst.HELP_ARGUMENT),
                               ("usx2yloader", CommonConst.HELP_ARGUMENT),
                               ("vxloader", CommonConst.HELP_ARGUMENT)]
