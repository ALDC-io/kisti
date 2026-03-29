#!/bin/bash
# Deploy KiSTI to Jetson: pull code, update session script + AccountsService, restart GDM
set -e
ssh -t aldc@192.168.22.131 bash -c "'
cd ~/repos/kisti && git pull --ff-only &&
echo aldc1234 | sudo -S cp scripts/kisti-session /usr/local/bin/kisti-session &&
echo aldc1234 | sudo -S cp scripts/jetson/kisti-session-user /var/lib/AccountsService/users/aldc &&
echo aldc1234 | sudo -S cp scripts/jetson/gdm-custom.conf /etc/gdm3/custom.conf &&
echo aldc1234 | sudo -S systemctl restart gdm &&
echo DEPLOYED
'"
