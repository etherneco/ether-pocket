/* GM1920 downstream UFS query ABI; also used by the local qbootctl build. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
static int device = -1;
struct query { uint32_t opcode; uint8_t idn, pad; uint16_t size; uint32_t value; };
int ufs_bsg_dev_open(void) {
    char cmdline[4096] = {0};
    FILE *f = fopen("/proc/cmdline", "r");
    if (!f) return -1;
    if (!fgets(cmdline, sizeof(cmdline), f)) { fclose(f); return -1; }
    fclose(f);
    if (!strstr(cmdline, "androidboot.serialno=548cb338 ")) { errno=ENODEV; return -1; }
    if (device < 0) device = open("/dev/sda", O_RDWR | O_CLOEXEC);
    struct query q = {.opcode=3, .size=4};
    if (device < 0 || ioctl(device, 0x5388, &q) || (q.value != 1 && q.value != 2)) return -1;
    return device;
}
void ufs_bsg_dev_close(void) { if (device >= 0) close(device); device=-1; }
int32_t set_boot_lun(uint8_t lun) {
    if (lun != 1 && lun != 2) return -1;
    if (ufs_bsg_dev_open() < 0) return -1;
    struct query q = {.opcode=4, .size=4, .value=lun};
    if (ioctl(device, 0x5388, &q)) return -1;
    q = (struct query){.opcode=3, .size=4};
    return ioctl(device, 0x5388, &q) || q.value != lun ? -1 : 0;
}
#ifdef UFS_QUERY_MAIN
int main(int argc, char **argv) {
    if (ufs_bsg_dev_open() < 0) { perror("UFS boot LUN query"); return 1; }
    if (argc == 2 && !strcmp(argv[1], "--restore-a")) {
        if (set_boot_lun(1)) { perror("Restore boot LUN A"); return 1; }
    } else if (argc != 1) return 1;
    struct query q = {.opcode=3, .size=4};
    if (ioctl(device, 0x5388, &q)) return 1;
    printf("UFS boot LUN: %u\n", q.value);
    ufs_bsg_dev_close(); return 0;
}
#endif
