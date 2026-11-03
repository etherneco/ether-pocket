#!/bin/sh
# Reuse the verified current UI resources; rebuild all C++ against media.h.
set -eu
if [ ! -d /opt/etherpocket/ethershell2-soft-blank-build ]; then
    cp -a /opt/etherpocket/ethershell2-cross-build /opt/etherpocket/ethershell2-soft-blank-build
fi
cd /opt/etherpocket/ethershell2-soft-blank-build
for target in ethershell_autogen/mocs_compilation.cpp src/main.cpp src/core.cpp src/distributor.cpp src/media.cpp src/pocket.cpp; do
    command=$(ninja -t commands "CMakeFiles/ethershell.dir/$target.o" | tail -1)
    test -n "$command"
    sh -c "$command"
done
command=$(ninja -t commands ethershell | tail -1)
test -n "$command"
sh -c "$command"
cp ethershell /mnt/c/projects.local/mobiam/build/ethershell-soft-blank-arm64
