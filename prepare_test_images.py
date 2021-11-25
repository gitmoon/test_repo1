# Initial data:
# ./common/files/privatekey.pem
# ./common/files/bad_kernel/welbilt_common_ui43.itb
# ./common/welbilt-firmware-image-welbilt-common-ui43.tar
# ./package/hardware-manager-1.0-r0_update.tar

import os
import sys
import tarfile
import shutil
from shutil import copyfile
import struct
import OpenSSL
from OpenSSL import crypto



IMAGE_TAR = "welbilt-firmware-image-welbilt-common-ui43.tar"
PACKAGE_HW_MANAGER_TAR = "hardware-manager-1.0-r0_update.tar"
PRIVATE_KEY = "common/files/privatekey.pem"
BAD_KERNEL_ITB = "common/files/bad_kernel/welbilt_common_ui43.itb"

COMMON_DIR = "common/"
PACKAGE_DIR = "package/"
TMP_IMAGE_DIR = "tmp_input_dir/"
TMP_PACKAGE_DIR = "tmp_package_dir/"
TMP_HW_MANAGER_DIR = "tmp_hw_manager/"
#-------Files image and package------------
VERSION_FILE_SIG = "version.txt.sig"
COMPATIBILITY_RULES = "compatibility_rules.txt" 
COMPATIBILITY_RULES_SIG = "compatibility_rules.txt.sig" 
KERNEL_ITB = "welbilt_common_ui43.itb"
KERNEL_ITB_SIG ="welbilt_common_ui43.itb.sig"
#-----Out directories------------------------------
DIR_MISS_FILE = "miss_file/"
DIR_BAD_KERNEL = "bad_kernel/"
DIR_CORRUPTED = "corrupted/"
#-------Generated files-----------------------------
CORRUPTED_FILE_INVALID_SIG = "welbilt-firmware-image-welbilt-common-ui43_invalid_sig.tar"
HWMANAGER_NO_PACKAGE = "hardware-manager-1.0-r0_update_no_package.tar"
HWMANAGER_NOT_COMPATIBLE = "hardware-manager-1.0-r0_update_not_compatible.tar" 
HWMANAGER_INVALID_SIG = "hardware-manager-1.0-r0_update_invalid_sig.tar"
HWMANAGER_BROKEN = "hardware-manager-1.0-r0_update_broken.tar"
#------------------------------------------
MISS_FILES_COLLECTION = ["version.txt", "version.txt.sig",
                         "compatibility_rules.txt", "compatibility_rules.txt.sig",
                         "welbilt_common_ui43.itb", "welbilt_common_ui43.itb.sig"
                         # exclude files welbilt-common-ui43.tar.gz
                         # exclude welbilt-common-ui43.tar.gz.sig
                         ]

IMAGE_FILES_COLLECTION = ["version.txt", "version.txt.sig",
                         "compatibility_rules.txt", "compatibility_rules.txt.sig",
                         "welbilt_common_ui43.itb", "welbilt_common_ui43.itb.sig",
                         "welbilt-common-ui43.tar.gz", "welbilt-common-ui43.tar.gz.sig"
                         ]

COLLECTION_HW_MANAGER_FULL = ["version.txt", "version.txt.sig",
                         "compatibility_rules.txt", "compatibility_rules.txt.sig",
                         "postinstall.sh", "postinstall.sh.sig",
                         "preinstall.sh", "preinstall.sh.sig",
                         "package.tar.gz", "package.tar.gz.sig"
                         ]        

COLLECTION_HW_MANAGER_NO_PACKAGE = ["version.txt", "version.txt.sig",
                         "compatibility_rules.txt", "compatibility_rules.txt.sig",
                         "postinstall.sh", "postinstall.sh.sig",
                         "preinstall.sh", "preinstall.sh.sig",
                         # exclude "package.tar.gz", 
                         "package.tar.gz.sig"
                         ] 
#---------------------------------------

def unpackFile(src, dest):
    tar = tarfile.open(src)
    tar.extractall(dest) 
    tar.close()
        
def packFiles(out_dir, out_file, input_dir, input_files):
    with tarfile.open(out_dir + out_file, "w") as tar:
        for name in input_files:
            tar.add(input_dir + name, name) 

def modifyFile(file):
    with open(file, 'r+b') as outfile:
        outfile.seek(0);
        outfile.write(struct.pack("BB",0x31,0x32));

def backupFile(file, newfile):
    copyfile(file, newfile)
    
def copyFile(file, newfile):
    copyfile(file, newfile)

def removeFile(file):
    if os.path.exists(file):
        os.remove(file)
    else:
        print("The file " + file + " does not exist")

def removeDir(dir):
    try:
        shutil.rmtree(dir)
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))
    

def restoreFile(file, newfile):
    copyfile(file, newfile)
    
def createDir(path):
    try:
        os.mkdir(path)
    except OSError:
        print ("Creation of the directory %s alrea" % path) 
    else:
        print ("Successfully created the directory %s " % path)        
 
def create_file(file_name):
    f= open(file_name,"w+")
 
def write_to_file(file_name, text):
    f = open(file_name, "r+")
    f.write(text)
    f.close()

#Ex using command line: 
#openssl dgst -sha256 -sign  privatekey.pem -out welbilt_common_ui43.itb.sig  welbilt_common_ui43.itb
def create_sign(file_name):
    key_file = open(PRIVATE_KEY, "r")
    key = key_file.read()
    key_file.close()
    password = ""
    
    if key.startswith('-----BEGIN '):
        pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, key)
    else:
        pkey = crypto.load_pkcs12(key, password).get_privatekey()

    with open(file_name, 'rb') as the_file:
        sign = OpenSSL.crypto.sign(pkey, the_file.read(), "sha256")
#    print("Sign:")      
#    print (sign.hex()) 
    
    with open(file_name + ".sig", 'w+b') as the_file_sig:
        the_file_sig.write(sign)


class Images:
    def __init__(self):
        print("Init Images")
        removeDir(DIR_MISS_FILE)
        removeDir(DIR_CORRUPTED)
        removeDir(DIR_BAD_KERNEL)
        createDir(TMP_IMAGE_DIR)
        createDir(DIR_CORRUPTED) 
        createDir(DIR_MISS_FILE)
        createDir(DIR_BAD_KERNEL)
        print("Unpack common/welbilt-firmware-image-welbilt-common-ui43.tar to a temporary directory")
        unpackFile(COMMON_DIR + IMAGE_TAR, TMP_IMAGE_DIR)        
   
    def __del__(self):
        print("Remove " + TMP_IMAGE_DIR)
        removeDir(TMP_IMAGE_DIR)
   
    def miss_file(self):
        MISS_FILE = IMAGE_TAR
        print("Create miss_file/welbilt-firmware-image-welbilt-common-ui43.tar")
        packFiles(DIR_MISS_FILE, MISS_FILE, TMP_IMAGE_DIR, MISS_FILES_COLLECTION)
        
#"SW.BSP.UPDATE.111 Negative: Firmware Update from Common UI file system on eMMC, invalid sig file in the new firmware package")
    def invalid_sig(self):
        print("create " + DIR_CORRUPTED + CORRUPTED_FILE_INVALID_SIG)
        VERSION_FILE_SIG_BACKUP = "version_backup.txt.sig"
        backupFile(TMP_IMAGE_DIR + VERSION_FILE_SIG, TMP_IMAGE_DIR + VERSION_FILE_SIG_BACKUP)
        modifyFile(TMP_IMAGE_DIR + VERSION_FILE_SIG)
        packFiles(DIR_CORRUPTED, CORRUPTED_FILE_INVALID_SIG, TMP_IMAGE_DIR, IMAGE_FILES_COLLECTION)
        restoreFile(TMP_IMAGE_DIR + VERSION_FILE_SIG_BACKUP,TMP_IMAGE_DIR + VERSION_FILE_SIG)
        removeFile(TMP_IMAGE_DIR + VERSION_FILE_SIG_BACKUP)
        
    def bad_kernel(self):
        BAD_KERNEL_FILE = IMAGE_TAR
        print("create " + DIR_BAD_KERNEL + BAD_KERNEL_FILE)
        KERNEL_ITB_BACKUP = "welbilt_common_ui43_backup.itb"
        KERNEL_ITB_SIG_BACKUP = "welbilt_common_ui43_backup.itb.sig"
        backupFile(TMP_IMAGE_DIR + KERNEL_ITB, TMP_IMAGE_DIR + KERNEL_ITB_BACKUP)
        backupFile(TMP_IMAGE_DIR + KERNEL_ITB_SIG, TMP_IMAGE_DIR + KERNEL_ITB_SIG_BACKUP)
        copyFile(BAD_KERNEL_ITB, TMP_IMAGE_DIR + KERNEL_ITB)
        create_sign(TMP_IMAGE_DIR + KERNEL_ITB)
        packFiles(DIR_BAD_KERNEL, BAD_KERNEL_FILE, TMP_IMAGE_DIR, IMAGE_FILES_COLLECTION)
        restoreFile(TMP_IMAGE_DIR + KERNEL_ITB_BACKUP, TMP_IMAGE_DIR + KERNEL_ITB)
        restoreFile(TMP_IMAGE_DIR + KERNEL_ITB_SIG_BACKUP, TMP_IMAGE_DIR + KERNEL_ITB_SIG)
        removeFile(TMP_IMAGE_DIR + KERNEL_ITB_BACKUP)
        removeFile(TMP_IMAGE_DIR + KERNEL_ITB_SIG_BACKUP)
        


class Packages:
    def __init__(self):
        print("Init Packages")
        createDir(TMP_PACKAGE_DIR)
        
    def __del__(self):
        print("Remove " + TMP_PACKAGE_DIR)
        removeDir(TMP_PACKAGE_DIR)

#"SW.BSP.UPDATE.254 Negative: Firmware Package Update from Common UI file system on eMMC, "two packages, one not compatible")
#"SW.BSP.UPDATE.254.1 Negative: Firmware Package Update from Common UI file system on eMMC,""two packages, one not compatible (forceUpdate)")
    def compatibility_issue(self):
        COMPATIBILITY_RULES_TEXT_1 = "test_\d\.\d\.\d\n" 
        removeDir(TMP_PACKAGE_DIR + TMP_HW_MANAGER_DIR)
        unpackFile(PACKAGE_DIR + PACKAGE_HW_MANAGER_TAR, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR)
        path_short = TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR+COMPATIBILITY_RULES
        removeFile(path_short)
        removeFile(TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR+COMPATIBILITY_RULES_SIG)
        create_file(path_short)
        write_to_file(path_short,COMPATIBILITY_RULES_TEXT_1)
        create_sign(path_short)
        packFiles(DIR_CORRUPTED, HWMANAGER_NOT_COMPATIBLE, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR, COLLECTION_HW_MANAGER_FULL)
        
#"SW.BSP.UPDATE.193 Negative: Firmware Package Update through USB Flash on eMMC, two packages,""one package with missing file"
    def missing_file(self):
        PACKAGE_TAR_GZ = "package.tar.gz"
        removeDir(TMP_PACKAGE_DIR + TMP_HW_MANAGER_DIR)
        unpackFile(PACKAGE_DIR + PACKAGE_HW_MANAGER_TAR, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR)    
        path_short = TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR+PACKAGE_TAR_GZ
        removeFile(path_short)
        packFiles(DIR_CORRUPTED, HWMANAGER_NO_PACKAGE, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR, COLLECTION_HW_MANAGER_NO_PACKAGE)       

#"SW.BSP.UPDATE.252 Negative: Firmware Package Update from Common UI file system on eMMC, " "two packages, one package with invalid sig file")
#"SW.BSP.UPDATE.252.1 Negative: Firmware Package Update from Common UI file system on eMMC, " "two packages, one package with invalid sig file (forceUpdate)")
    def invalid_sig(self):
        removeDir(TMP_PACKAGE_DIR + TMP_HW_MANAGER_DIR)
        unpackFile(PACKAGE_DIR + PACKAGE_HW_MANAGER_TAR, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR)
        modifyFile(TMP_PACKAGE_DIR + TMP_HW_MANAGER_DIR + VERSION_FILE_SIG)
        packFiles(DIR_CORRUPTED, HWMANAGER_INVALID_SIG, TMP_PACKAGE_DIR+TMP_HW_MANAGER_DIR, COLLECTION_HW_MANAGER_FULL)        

    def broken(self):
        create_file(DIR_CORRUPTED + HWMANAGER_BROKEN)

def check_production_init():
    DIR_ROOT = "files_for_emulated_flash_drive/"
    DIR_PRODUCTION = "flash_data_prod/"
    DIR_BSPUPDATE = "bsp_update"
    os.chdir(DIR_ROOT + DIR_PRODUCTION + DIR_BSPUPDATE)
    
    INPUT_FILES = [COMMON_DIR + IMAGE_TAR, PRIVATE_KEY, PACKAGE_DIR+PACKAGE_HW_MANAGER_TAR, BAD_KERNEL_ITB]
    for file in INPUT_FILES:
        file_exists = os.path.exists(file)
        if file_exists == False:
            raise Exception("Can't find the file " + file)
    print("Input files for generating production images is ok ")


if __name__ == "__main__":

    try:
        check_production_init()
    except Exception as e:
        print("Init error: " + str(e))
    else:
        image = Images()
        image.miss_file()
        image.invalid_sig()
        image.bad_kernel()
        
        
        package = Packages()
        package.compatibility_issue()
        package.missing_file()
        package.invalid_sig()
        package.broken()
 