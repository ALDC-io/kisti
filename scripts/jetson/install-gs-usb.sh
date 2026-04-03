#!/bin/bash
# Build and install usb_8dev kernel module for 5.15.148-tegra
# Enables 8devices Korlan USB2CAN adapter (0483:1234) on Jetson Orin Nano
# The Korlan presents as a native USB CAN device (not serial/slcan)
# Run on Jetson as: bash install-gs-usb.sh

set -e

KVER="5.15.148-tegra"
KDIR="/lib/modules/${KVER}/build"
BUILD_DIR="$HOME/usb_8dev_build"

echo "=== usb_8dev build for ${KVER} ==="

# 1. Download source
mkdir -p "$BUILD_DIR"
echo "[1/5] Downloading usb_8dev.c from kernel 5.15.148..."
wget -q "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/net/can/usb/usb_8dev.c?h=v5.15.148" \
     -O "$BUILD_DIR/usb_8dev.c"
echo "      $(wc -l < "$BUILD_DIR/usb_8dev.c") lines downloaded"

# 2. Write Makefile
cat > "$BUILD_DIR/Makefile" << 'MAKEFILE'
obj-m := usb_8dev.o
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
echo "      Build complete: $(ls usb_8dev.ko)"

# 4. Install
echo "[3/5] Installing module..."
sudo make -C "$KDIR" M="$BUILD_DIR" modules_install
sudo depmod -a

# 5. Load now
echo "[4/5] Loading module..."
sudo modprobe usb_8dev

# 6. Persist across reboots
echo "[5/5] Adding to /etc/modules-load.d/ for auto-load on boot..."
echo "usb_8dev" | sudo tee /etc/modules-load.d/usb_8dev.conf > /dev/null

# 7. Write udev rule: bring up can interface at 1Mbit/s on plug-in
echo "      Writing udev rule for auto-bringup at 1Mbit/s..."
sudo tee /etc/udev/rules.d/80-can-usb.rules > /dev/null << 'UDEV'
# 8devices Korlan USB2CAN (0483:1234) — auto-configure at 1Mbit/s on plug-in
ACTION=="add", SUBSYSTEM=="net", KERNEL=="can*", \
  ATTRS{idVendor}=="0483", ATTRS{idProduct}=="1234", \
  RUN+="/bin/sh -c 'ip link set %k type can bitrate 1000000 && ip link set %k up'"
UDEV
sudo udevadm control --reload-rules

# 8. Bring up the new interface for this session (udev won't fire retroactively)
echo ""
echo "=== Configuring CAN interface ==="
# unplug/replug triggers udev; for now configure manually
CAN_IF=$(ip link show | grep -o 'can[0-9]*' | grep -v '^can0$' | head -1)
if [ -n "$CAN_IF" ]; then
    sudo ip link set "$CAN_IF" down 2>/dev/null || true
    sudo ip link set "$CAN_IF" type can bitrate 1000000
    sudo ip link set "$CAN_IF" up
    echo "Brought up $CAN_IF at 1Mbit/s"
else
    echo "Korlan not yet enumerated as CAN interface."
    echo "Unplug and replug the USB adapter — udev will bring it up automatically."
fi

echo ""
echo "=== Final state ==="
ip -details link show type can
echo ""
echo "Done. usb_8dev is installed and will auto-load on boot."
echo "Korlan will auto-configure at 1Mbit/s on every plug-in."
echo ""
echo "NOTE: The slcand/slcan approach in your setup notes will NOT work —"
echo "the Korlan (0483:1234) is a native USB CAN device, not serial."
echo "Use 'can1' (or whatever interface appears above) with python-can:"
echo "  bus = can.interface.Bus(channel='can1', bustype='socketcan')"
