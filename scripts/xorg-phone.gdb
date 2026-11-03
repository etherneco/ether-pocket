set pagination off
set confirm off
set debuginfod enabled off
set sysroot target:
set architecture aarch64
target remote | /mnt/c/Windows/System32/OpenSSH/ssh.exe -i C:/projects.local/mobiam/build/etherpocket_ed25519 -o UserKnownHostsFile=C:/projects.local/mobiam/build/mobian-known-hosts -o BatchMode=yes root@10.77.0.2 /run/gdbserver - /usr/lib/xorg/Xorg :0 -nolisten tcp vt7 -noreset
continue
backtrace
info registers pc x0 x1 x2 x3
x/10i $pc
kill
quit
