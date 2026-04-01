#!/usr/bin/env bash
# Install whisper-server as a systemd service on Jetson
set -e
sudo cp ~/repos/kisti/scripts/jetson/whisper-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now whisper-server
systemctl status whisper-server --no-pager
