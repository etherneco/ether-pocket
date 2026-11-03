#!/bin/sh
# Build-time replacement for Mobian's default-password helper.
set -eu
username=$1
adduser --gecos "$username" --disabled-password --shell /bin/bash "$username"
for group in sudo adm bluetooth plugdev video input render; do
    if getent group "$group" >/dev/null; then adduser "$username" "$group"; fi
done
test -s /etc/etherpocket/user-password.hash
printf '%s:' "$username" | cat - /etc/etherpocket/user-password.hash | chpasswd -e
rm /etc/etherpocket/user-password.hash
