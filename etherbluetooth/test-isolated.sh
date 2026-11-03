#!/bin/sh
# Tests use a private D-Bus daemon, never the hardware's system bus.
set -eu
test_binary=${1:-./integration-test}
test_config=$(mktemp -d)
trap 'rm -r -- "$test_config"' EXIT
export XDG_CONFIG_HOME="$test_config"
export ETHERBLUETOOTH_TEST_BUS=1
dbus-run-session -- sh -c 'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec "$1"' sh "$test_binary"
