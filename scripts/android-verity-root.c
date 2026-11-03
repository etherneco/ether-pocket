/* Recreate the verified stock system_b verity table before Android switch_root. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <linux/dm-ioctl.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
static unsigned char buffer[4096] __attribute__((aligned(8)));
static struct dm_ioctl *request(void) {
    memset(buffer,0,sizeof(buffer));
    struct dm_ioctl *d=(void *)buffer;
    d->version[0]=4; d->version[1]=0; d->version[2]=0;
    d->data_size=sizeof(buffer); d->data_start=sizeof(*d);
    strcpy(d->name,"vroot"); d->flags=DM_READONLY_FLAG;
    return d;
}
int main(void) {
    FILE *f=fopen("/sys/class/block/sda14/uevent","r");
    char identity[1024]={0};
    if (!f) return 1;
    size_t size=fread(identity,1,sizeof(identity)-1,f); fclose(f);
    if (!size || !strstr(identity,"PARTNAME=system_b\n")) return 1;
    int fd=open("/dev/mapper/control",O_RDWR);
    if (fd<0) { perror("device-mapper control"); return 1; }
    struct dm_ioctl *d=request();
    if (ioctl(fd,DM_DEV_CREATE,d)) { perror("create vroot"); return 1; }
    d=request(); d->target_count=1;
    struct dm_target_spec *target=(void *)(buffer+d->data_start);
    target->length=7401432;
    strcpy(target->target_type,"verity");
    const char *table="1 /dev/sda14 /dev/sda14 4096 4096 925179 925179 sha1 "
      "878af769f9396485e7ac1954684d5fa0e8b1f9ce 92627205181a7c34ad5a6635f4490d70cdd6eee0 "
      "10 restart_on_corruption ignore_zero_blocks use_fec_from_device /dev/sda14 "
      "fec_roots 2 fec_blocks 932465 fec_start 932465";
    strcpy((char *)(target+1),table);
    target->next=(sizeof(*target)+strlen(table)+1+7)&~7u;
    if (ioctl(fd,DM_TABLE_LOAD,d)) { perror("load verity table"); return 1; }
    d=request();
    if (ioctl(fd,DM_DEV_SUSPEND,d)) { perror("resume vroot"); return 1; }
    close(fd); return 0;
}
