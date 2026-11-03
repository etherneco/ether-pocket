/* Read the active diagnostic scanout buffer; never modify display state. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_mode.h>
int main(void) {
    int fd = open("/dev/dri/card0", O_RDWR);
    if (fd < 0) { perror("open"); return 1; }
    if (drmSetClientCap(fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1)) {
        perror("universal planes"); return 1;
    }
    drmModePlaneRes *planes = drmModeGetPlaneResources(fd);
    uint32_t fb_id = 0;
    if (!planes) return 1;
    for (uint32_t i = 0; i < planes->count_planes; i++) {
        drmModePlane *p = drmModeGetPlane(fd, planes->planes[i]);
        if (p && p->crtc_id && p->fb_id) fb_id = p->fb_id;
        drmModeFreePlane(p);
        if (fb_id) break;
    }
    drmModeFreePlaneResources(planes);
    drmModeFB *fb = fb_id ? drmModeGetFB(fd, fb_id) : NULL;
    if (!fb || fb->bpp != 32 || !fb->handle) {
        fprintf(stderr, "No accessible 32-bit active framebuffer\n"); return 1;
    }
    struct drm_mode_map_dumb map = {.handle = fb->handle};
    if (drmIoctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) { perror("map ioctl"); return 1; }
    size_t size = (size_t)fb->pitch * fb->height;
    uint8_t *pixels = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, map.offset);
    if (pixels == MAP_FAILED) { perror("mmap"); return 1; }
    printf("P6\n%u %u\n255\n", fb->width, fb->height);
    uint8_t *row = malloc((size_t)fb->width * 3);
    if (!row) return 1;
    for (uint32_t y = 0; y < fb->height; y++) {
        for (uint32_t x = 0; x < fb->width; x++) {
            uint8_t *p = pixels + (size_t)y * fb->pitch + x * 4;
            row[x * 3] = p[2]; row[x * 3 + 1] = p[1]; row[x * 3 + 2] = p[0];
        }
        if (fwrite(row, 3, fb->width, stdout) != fb->width) return 1;
    }
    free(row); munmap(pixels, size); drmModeFreeFB(fb); close(fd); return 0;
}
