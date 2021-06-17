cd plutosdr-fw
git apply ../patches/fw.diff
cd hdl
git apply ../../patches/hdl.diff
cd ../linux
git apply ../../patches/linux.diff
cd ../u-boot-xlnx
git apply ../../patches/u-boot-xlnx.diff
cd ../buildroot
git apply ../../patches/buildroot.diff
cd ../..
