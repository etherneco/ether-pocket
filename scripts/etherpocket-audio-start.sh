#!/bin/sh
set -eu
if grep -q '^q6_dlkm .* Unloading ' /proc/modules; then
 echo 'Audio module is stuck unloading; a full hardware restart is required.' >&2
 exit 1
fi
# Keep ADSP recovery local rather than restarting the entire phone.
for device in /sys/bus/msm_subsys/devices/subsys*; do
 if [ "$(cat "$device/name")" = adsp ]; then
  echo RELATED > "$device/restart_level"
 fi
done
for module in q6_pdr_dlkm q6_notifier_dlkm apr_dlkm q6_dlkm \
 pinctrl_wcd_dlkm wcd_core_dlkm wcd9xxx_dlkm swr_dlkm swr_ctrl_dlkm \
 mbhc_dlkm wcd934x_dlkm wcd9360_dlkm wsa881x_dlkm tfa9894_dlkm \
 stub_dlkm hdmi_dlkm platform_dlkm native_dlkm machine_dlkm adsp_loader_dlkm; do
 modprobe "$module"
done
echo 1 > /sys/kernel/boot_adsp/boot
for attempt in $(seq 1 30); do
 if [ -e /dev/snd/controlC0 ]; then
  # Set the real 24-bit backend before PipeWire probes PCM capabilities.
  /usr/local/sbin/etherpocket-audio-route
  exit 0
 fi
 sleep 1
done
cat /proc/asound/cards >&2
exit 1
