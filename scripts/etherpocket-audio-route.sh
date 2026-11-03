#!/bin/sh
set -eu
amixer -q -c 0 cset "name=QUAT_MI2S_RX Channels" Two
amixer -q -c 0 cset "name=QUAT_MI2S_RX Format" S24_LE
amixer -q -c 0 cset "name=QUAT_MI2S_RX SampleRate" KHZ_48
amixer -q -c 0 cset "name=stereo Profile" speaker
amixer -q -c 0 cset "name=Tfa Mute" 0
amixer -q -c 0 cset "name=QUAT_MI2S_RX Audio Mixer MultiMedia1" on,on
