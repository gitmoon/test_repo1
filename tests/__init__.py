import os
import sys

PROJECT_NAME = "WB_Common_UI_Tests_Automation"
DIR_PATH = os.getcwd()
DIR_PATH = DIR_PATH[:DIR_PATH.find(PROJECT_NAME) + len(PROJECT_NAME)]
sys.path.append(DIR_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "comm_support_lib")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "comm_support_lib", "comm_interfaces")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "comm_support_lib", "common")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "comm_support_lib", "config")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "comm_support_lib", "hw_drivers")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "utils")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "utils", "common")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "utils", "config")
sys.path.append(CAN_HELPER_PATH)

CAN_HELPER_PATH = os.path.join(DIR_PATH, "tests")
sys.path.append(CAN_HELPER_PATH)
