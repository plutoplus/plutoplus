cd plutosdr-fw
git diff --ignore-submodules > ../patches/fw.diff
cd hdl
git diff > ../../patches/hdl.diff
cd ../linux
git diff > ../../patches/linux.diff
cd ../u-boot-xlnx
git diff > ../../patches/u-boot-xlnx.diff
cd ../buildroot
git diff > ../../patches/buildroot.diff
cd ../..
