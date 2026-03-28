#!/bin/bash
# Fix GDM to auto-login as aldc with KiSTI session
# Run with: sudo bash ~/repos/kisti/scripts/fix-gdm-session.sh

set -e

echo "=== Configuring GDM autologin with KiSTI session ==="

# 1. GDM config
cat > /etc/gdm3/custom.conf << 'GDMCONF'
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=aldc
DefaultSession=kisti-session

[security]

[xdmcp]

[chooser]

[debug]
GDMCONF
echo "GDM config written"

# 2. AccountsService user file
mkdir -p /var/lib/AccountsService/users
cat > /var/lib/AccountsService/users/aldc << 'ACCT'
[User]
Session=kisti-session
SystemAccount=false
ACCT
echo "AccountsService user file written"

# 3. Update kisti-session script from repo
cp /home/aldc/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session
chmod +x /usr/local/bin/kisti-session
echo "kisti-session script updated"

# 4. Verify
echo ""
echo "=== Verify ==="
echo "GDM config:"
grep -E 'AutomaticLogin|DefaultSession' /etc/gdm3/custom.conf
echo "AccountsService:"
cat /var/lib/AccountsService/users/aldc
echo "Session script:"
head -1 /usr/local/bin/kisti-session
echo ""
echo "=== Done. Reboot to apply: sudo reboot ==="
