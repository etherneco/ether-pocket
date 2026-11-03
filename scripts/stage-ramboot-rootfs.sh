#!/bin/bash
# Prepare only the build overlay. RAM boot is a separate, verified operation.
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
recipes=/opt/etherpocket/mobian-recipes
overlay=$recipes/overlays/etherpocket
mkdir -p "$overlay/root/.ssh" "$overlay/etc/systemd/system/multi-user.target.wants" \
 "$overlay/usr/local/sbin" "$overlay/etc/lightdm/lightdm.conf.d" \
 "$overlay/etc/NetworkManager/conf.d" "$overlay/etc/xdg/autostart"
cp "$workspace/config/etherpocket-ramboot-init" "$overlay/init"
cp "$workspace/scripts/etherpocket-usb-debug.sh" "$overlay/usr/local/sbin/etherpocket-usb-debug"
chmod 755 "$overlay/init" "$overlay/usr/local/sbin/etherpocket-usb-debug"
cp "$workspace/config/etherpocket-usb-debug.service" "$overlay/etc/systemd/system/"
ln -sfn /etc/systemd/system/etherpocket-usb-debug.service \
 "$overlay/etc/systemd/system/multi-user.target.wants/etherpocket-usb-debug.service"
for service in systemd-repart systemd-growfs-root; do
 ln -sfn /dev/null "$overlay/etc/systemd/system/$service.service"
done
test -s "$workspace/build/etherpocket_ed25519.pub"
cp "$workspace/build/etherpocket_ed25519.pub" "$overlay/root/.ssh/authorized_keys"
chmod 700 "$overlay/root/.ssh"
chmod 600 "$overlay/root/.ssh/authorized_keys"
cat > "$overlay/etc/lightdm/lightdm.conf.d/95-etherpocket-ramtest.conf" <<'EOF'
# Temporary RAM test image only; no persistence on phone storage.
[Seat:*]
autologin-user=mobian
autologin-user-timeout=0
autologin-session=xfce
EOF
cat > "$overlay/etc/NetworkManager/conf.d/90-etherpocket-usb.conf" <<'EOF'
[keyfile]
unmanaged-devices=interface-name:usb0;interface-name:rndis0
EOF
cat > "$overlay/etc/xdg/autostart/etherpocket-mobile.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=EtherPocket mobile setup
Exec=sh -c "sleep 10; etherair-x11 mobile --dpi 180"
OnlyShowIn=XFCE;
EOF
cat > "$overlay/etc/xdg/autostart/etherpocket-evidence.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=EtherPocket X11 acceptance evidence
Exec=sh -c "sleep 30; etherair-x11 diagnose --output /home/mobian/phone-x11-evidence.json"
OnlyShowIn=XFCE;
EOF
# Also accommodate a recipe that was parsed before the relative-path fix.
if [ ! -e "$recipes/include/overlays" ]; then
 ln -s ../overlays "$recipes/include/overlays"
fi
cp "$workspace/scripts/setup-rootfs-user.sh" "$recipes/scripts/setup-user.sh"
chmod 755 "$recipes/scripts/setup-user.sh"
