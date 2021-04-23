# PlutoSDR+
The repo maintain the firmware of PlutoSDR+

## How to upgrade the firmware

1. You can download the latest firmware from here
2. Unzip the files
3. Put *.frm files into the storage disk named "PlutoSDR"

### DFU Upgrade
If you device is not responding anymore, you have to apply DFU procedure to unbrick it.
1. Remove the screws and open up the device.
2. Short URST with GPIO52
3. Press DFU while plugin the power
4. Download the firmware and unzip it.
5. Install dfu utility
5. Run DFU utility with the following command:
   ```
   dfu-tool -a 0 -write boot.dfu
   dfu-tool -a 1 -write pluto.dfu
   ```

## How to build firmware manually
1. Clone this repo
2. Download the source code via 'git submodule update --init'
3. Apply the diff to each subfolder
   ```
   cd plutosdr-fw
   git apply ../patches/fw.diff
   
   cd hdl
   git apply ../../hdl.diff
   cd ..
   
   cd linux
   git apply ../../linux.diff
   cd ..
   
   cd u-boot-xlnx
   git apply ../../u-boot-xlnx.diff
   cd ..
   
   ```
4. Build the code via 'make' in plutosdr-fw folder

In case you hit the error, please search the internet on PlutoSDR firmware build. It is identical.
