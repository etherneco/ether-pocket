#!/bin/bash
# Run on native Mobian/Debian ARM64, never through adb shell or proot.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
packages=(xserver-xorg-core xinit xauth x11-xserver-utils xinput
  xserver-xorg-input-libinput xfce4 xfce4-terminal openbox lightdm
  lightdm-gtk-greeter mesa-utils mesa-utils-bin libgl1-mesa-dri
  libegl-mesa0 libgles2 x11-utils onboard xfce4-appfinder
  xfce4-power-manager wmctrl python3 unclutter-xfixes util-linux)
case "${1:-}" in
  '') printf 'Preview only; run on native ARM64 Linux with --apply.\n'
      printf 'APT packages: %s\n' "${packages[*]}"
      printf 'xrandr is supplied by x11-xserver-utils on Debian.\n'; exit 0 ;;
  --apply) ;;
  *) echo 'Usage: install-x11.sh [--apply]' >&2; exit 2 ;;
esac
[[ $EUID == 0 ]] || { echo 'Use sudo on the native Linux target.' >&2; exit 1; }
[[ $(uname -m) == aarch64 && $(dpkg --print-architecture) == arm64 ]] || {
  echo 'Native ARM64 required.' >&2; exit 1; }
[[ -f /etc/debian_version && ! -e /system/build.prop ]] || {
  echo 'Mobian/Debian target required; Android is not supported.' >&2; exit 1; }
if systemd-detect-virt --container --quiet || [[ -n ${PROOT_TMP_DIR:-} ]]; then
  echo 'Container/proot is not an accepted target.' >&2; exit 1
fi
compgen -G '/dev/dri/card[0-9]*' >/dev/null || {
  echo 'BLOCKED: no kernel DRM card; resolve kernel/display support first.' >&2; exit 1; }
[[ -e /sys/class/tty/tty0 ]] || {
  echo 'BLOCKED: no kernel virtual-terminal support for local LightDM/Xorg.' >&2; exit 1; }
record=/var/lib/etherpocket/install-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$record"
# Keep the user's repositories and foundation; do not substitute an OS.
cp /etc/os-release "$record/os-release"
cp -a /etc/apt "$record/apt-before"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"
command -v xrandr >/dev/null
test -f /usr/share/xsessions/xfce.desktop
test -f /usr/share/xgreeters/lightdm-gtk-greeter.desktop
mkdir -p /etc/lightdm/lightdm.conf.d /etc/xdg/autostart /usr/local/bin
install -m 644 config/90-etherpocket.conf /etc/lightdm/lightdm.conf.d/90-etherpocket.conf
install -m 755 scripts/etherair-x11.py /usr/local/bin/etherair-x11
install -m 755 ethershell/packaging/ethershell-touch-cursor /usr/bin/ethershell-touch-cursor
install -m 644 ethershell/packaging/ethershell-touch-cursor.desktop /etc/xdg/autostart/ethershell-touch-cursor.desktop
install -m 644 config/etherair-x11.desktop /etc/xdg/autostart/etherair-x11.desktop
install -m 644 config/etherpocket-launcher.desktop /usr/share/applications/etherpocket-launcher.desktop
if [[ -e /etc/X11/default-display-manager ]]; then
  cp -a /etc/X11/default-display-manager "$record/default-display-manager.before"
fi
printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
# Disable competing managers, without killing the current session.
for manager in gdm3 sddm phosh greetd; do
  if systemctl cat "$manager.service" >/dev/null 2>&1; then
    systemctl disable "$manager.service"
  fi
done
systemctl enable --force lightdm.service
systemctl set-default graphical.target
dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > "$record/packages.tsv"
apt-cache policy > "$record/apt-policy.txt"
sha256sum scripts/etherair-x11.py config/90-etherpocket.conf > "$record/config.sha256"
echo 'Installed. Log out/reboot when ready; no current session was restarted.'
echo 'Verify LightDM effective settings: lightdm --show-config'
echo 'In the physical session: etherair-x11 diagnose --output evidence-x11.json'
