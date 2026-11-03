#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <xf86drmMode.h>
int main(void) {
    int fd = open("/dev/dri/card0", O_RDWR);
    if (fd < 0) { perror("DRM open"); return 1; }
    drmModeRes *r = drmModeGetResources(fd);
    if (!r) { perror("DRM resources"); return 1; }
    for (int i = 0; i < r->count_connectors; i++) {
        drmModeConnector *c = drmModeGetConnector(fd, r->connectors[i]);
        if (!c) continue;
        for (int j = 0; j < c->count_modes; j++) {
            drmModeModeInfo *m = &c->modes[j];
            printf("connector=%u name=%s refresh=%u clock=%u H=%u,%u,%u,%u V=%u,%u,%u,%u flags=%u\n",
                   c->connector_id, m->name, m->vrefresh, m->clock,
                   m->hdisplay, m->hsync_start, m->hsync_end, m->htotal,
                   m->vdisplay, m->vsync_start, m->vsync_end, m->vtotal, m->flags);
        }
        drmModeFreeConnector(c);
    }
    drmModeFreeResources(r); close(fd); return 0;
}
