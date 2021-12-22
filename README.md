# Getting Started
1. "flash_data" folder should be placed to the board according to readme inside "files_for_emulated_flash_drive";
2. "comm_support_lib\config\config.py" file should be configured according to user manual;
3. "tests\config\config.py" file should be configured according to user manual.



# Generate images
1. Put the new production image "welbilt-firmware-image-welbilt-common-ui43.tar" into the directory
  .\files_for_emulated_flash_drive\source\prod\common
2. Execute command 
   python .\prepare_test_images.py
3. Generated files can be found in directory
   .\files_for_emulated_flash_drive\flash_data_prod_auto\
4. The directory "files_for_emulated_flash_drive\source\"  contains source files used to create test images
