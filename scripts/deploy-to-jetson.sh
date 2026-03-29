#!/bin/bash
# Deploy kisti-session to Jetson and restart
ssh -t aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && sudo cp scripts/kisti-session /usr/local/bin/kisti-session && sudo systemctl restart gdm && echo 'Deployed and restarting'"
