#!/bin/bash
# Build and install gs_usb kernel module for 5.15.148-tegra
# Enables STMicro USB2CAN adapter (0483:1234) on Jetson Orin Nano
# Run on Jetson as: bash install-gs-usb.sh

set -e

KVER="5.15.148-tegra"
KDIR="/lib/modules/${KVER}/build"
BUILD_DIR="$HOME/gs_usb_build"

echo "=== gs_usb build for ${KVER} ==="

# 1. Download source
mkdir -p "$BUILD_DIR"
echo "[1/5] Downloading gs_usb.c from kernel 5.15.148..."
wget -q "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/net/can/usb/gs_usb.c?h=v5.15.148" \
     -O "$BUILD_DIR/gs_usb.c"
echo "      $(wc -l < "$BUILD_DIR/gs_usb.c") lines downloaded"

# 2. Write Makefile
cat > "$BUILD_DIR/Makefile" << 'MAKEFILE'
obj-m := gs_usb.o
KDIR := /lib/modules/5.15.148-tegra/build

all:
	make -C $(KDIR) M=$(CURDIR) modules

clean:
	make -C $(KDIR) M=$(CURDIR) clean
MAKEFILE

# 3. Build
echo "[2/5] Building module (requires sudo)..."
cd "$BUILD_DIR"
sudo make
echo "      Build complete: $(ls gs_usb.ko)"

# 4. Install
echo "[3/5] Installing module..."
sudo make -C "$KDIR" M="$BUILD_DIR" modules_install
sudo depmod -a

# 5. Load now
echo "[4/5] Loading module..."
sudo modprobe gs_usb

# 6. Persist across reboots
echo "[5/5] Adding to /etc/modules-load.d/ for auto-load on boot..."
echo "gs_usb" | sudo tee /etc/modules-load.d/gs_usb.conf > /dev/null

# 7. Write udev rule: bring up can1 at 1Mbit/s on plug-in
echo "      Writing udev rule for auto-bringup at 1Mbit/s..."
sudo tee /etc/udev/rules.d/80-can-usb.rules > /dev/null << 'UDEV'
# STMicro USB2CAN (0483:1234) — auto-configure CAN interface at 1Mbit/s
ACTION=="add", SUBSYSTEM=="net", KERNEL=="can*", \
  ATTRS{idVendor}=="0483", ATTRS{idProduct}=="1234", \
  RUN+="/bin/sh -c 'ip link set %k type can bitrate 1000000 && ip link set %k up'"
UDEV
sudo udevadm control --reload-rules

# 8. Bring up can1 manually for this session (udev won't fire retroactively)
echo ""
echo "=== Configuring CAN interface ==="
CAN_IF=$(ip link show | grep -o 'can[0-9]*' | grep -v can0 | head -1)
if [ -n "$CAN_IF" ]; then
    sudo ip link set "$CAN_IF" down 2>/dev/null || true
    sudo ip link set "$CAN_IF" type can bitrate 1000000
    sudo ip link set "$CAN_IF" up
    echo "Brought up $CAN_IF at 1Mbit/s"
else
    echo "No new CAN interface found yet — unplug/replug the adapter if needed"
fi

echo ""
echo "=== Final state ==="
ip -details link show type can
echo ""
echo "Done. gs_usb is installed and will auto-load on boot."
echo "USB adapter will auto-configure at 1Mbit/s on plug-in."
