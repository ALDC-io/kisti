#!/bin/bash
# Deploy KiSTI to Jetson: pull code, relaunch on display
set -e
ssh aldc@192.168.22.131 'cd ~/repos/kisti && git pull --ff-only && bash scripts/jetson/relaunch.sh'
