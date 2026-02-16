#!/usr/bin/env python3
"""KiSTI

Visual telemetry prototype for Kenwood Excelon head unit (800x480).
Runs on Jetson Orin with X11 display.

Usage:
    python3 main.py                  # Windowed 800x480
    python3 main.py --fullscreen     # Fullscreen
    python3 main.py --display :0     # Specify X display
    python3 main.py --platform eglfs # Use eglfs instead of xcb

Prerequisites:
    pip install PySide6
    sudo apt-get install libxcb-cursor0  # Required for xcb platform
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="KiSTI")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen mode")
    parser.add_argument("--display", type=str, default=None, help="X11 display (e.g. :0)")
    parser.add_argument("--platform", type=str, default=None,
                        help="Qt platform plugin (xcb, eglfs, linuxfb, offscreen)")
    args = parser.parse_args()

    if args.display:
        os.environ["DISPLAY"] = args.display

    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = args.platform

    # Verify DISPLAY is set (unless using a non-X11 platform)
    non_x11 = os.environ.get("QT_QPA_PLATFORM", "") in ("eglfs", "linuxfb", "offscreen")
    if "DISPLAY" not in os.environ and not non_x11:
        print("ERROR: DISPLAY environment variable not set.")
        print("Try: export DISPLAY=:0 && python3 main.py")
        print("Or:  python3 main.py --platform eglfs")
        sys.exit(1)

    # Import Qt after environment is configured
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication(sys.argv)

    window = MainWindow(fullscreen=args.fullscreen)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
