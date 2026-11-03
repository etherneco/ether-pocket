/* Native DRM/KMS boot menu. No disk writes and no OS switching in this program. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>
#include <drm_mode.h>

struct surface { uint32_t handle, fb, pitch; uint64_t size; void *map; };
struct selection { int selected, armed, ignore_power; };
static int fd = -1;
static uint32_t connector_id, crtc_id, plane_id;

static int key(struct selection *s, unsigned code, int value) {
    if ((code == KEY_VOLUMEUP || code == KEY_VOLUMEDOWN) && value == 1) {
        s->selected ^= 1;
        return 1;
    }
    if (code == KEY_POWER) {
        if (s->ignore_power) { if (!value) s->ignore_power = 0; return 0; }
        if (value == 1) s->armed = 1;
        if (!value && s->armed) return 2;
    }
    return 0;
}

static int selftest(void) {
    struct selection s = {0};
    if (key(&s, KEY_VOLUMEDOWN, 1) != 1 || s.selected != 1) return 1;
    if (key(&s, KEY_VOLUMEDOWN, 2) || s.selected != 1) return 1;
    if (key(&s, KEY_VOLUMEUP, 1) != 1 || s.selected != 0) return 1;
    if (key(&s, KEY_POWER, 0)) return 1;
    if (key(&s, KEY_POWER, 1) || key(&s, KEY_POWER, 0) != 2) return 1;
    s = (struct selection){.ignore_power = 1};
    if (key(&s, KEY_POWER, 1) || key(&s, KEY_POWER, 0) || s.ignore_power) return 1;
    if (key(&s, KEY_POWER, 1) || key(&s, KEY_POWER, 0) != 2) return 1;
    puts("Boot-menu key state tests passed");
    return 0;
}

static uint32_t property(uint32_t object, uint32_t type, const char *name, uint64_t *value) {
    drmModeObjectProperties *props = drmModeObjectGetProperties(fd, object, type);
    uint32_t result = 0;
    if (!props) return 0;
    for (uint32_t i = 0; i < props->count_props; i++) {
        drmModePropertyRes *p = drmModeGetProperty(fd, props->props[i]);
        if (p && !strcmp(p->name, name)) {
            result = p->prop_id;
            if (value) *value = props->prop_values[i];
        }
        drmModeFreeProperty(p);
        if (result) break;
    }
    drmModeFreeObjectProperties(props);
    return result;
}

static int add(drmModeAtomicReq *req, uint32_t obj, uint32_t type, const char *name, uint64_t value) {
    uint32_t p = property(obj, type, name, NULL);
    if (!p || drmModeAtomicAddProperty(req, obj, p, value) < 0) {
        fprintf(stderr,"Missing/invalid atomic property %s\n",name); return -1;
    }
    return 0;
}

static int find_panel(drmModeModeInfo *mode) {
    drmModeRes *res = drmModeGetResources(fd);
    int pipe = -1;
    if (!res) return -1;
    for (int i = 0; i < res->count_connectors && !connector_id; i++) {
        drmModeConnector *c = drmModeGetConnector(fd, res->connectors[i]);
        if (c && c->connector_type == DRM_MODE_CONNECTOR_DSI && c->connection == DRM_MODE_CONNECTED) {
            for (int m = 0; m < c->count_modes; m++) {
                if (c->modes[m].hdisplay == 1440 && c->modes[m].vdisplay == 3120 && c->modes[m].vrefresh == 60) {
                    *mode = c->modes[m]; connector_id = c->connector_id; break;
                }
            }
            for (int e = 0; e < c->count_encoders && connector_id && pipe < 0; e++) {
                drmModeEncoder *enc = drmModeGetEncoder(fd, c->encoders[e]);
                if (enc) {
                    for (int j = 0; j < res->count_crtcs; j++) {
                        if (enc->possible_crtcs & (1u << j)) { pipe = j; crtc_id = res->crtcs[j]; break; }
                    }
                }
                drmModeFreeEncoder(enc);
            }
        }
        drmModeFreeConnector(c);
    }
    drmModeFreeResources(res);
    if (pipe < 0) return -1;
    drmModePlaneRes *planes = drmModeGetPlaneResources(fd);
    if (!planes) return -1;
    for (uint32_t i = 0; i < planes->count_planes; i++) {
        drmModePlane *p = drmModeGetPlane(fd, planes->planes[i]);
        uint64_t type = UINT64_MAX;
        if (p && (p->possible_crtcs & (1u << pipe)) &&
            property(p->plane_id, DRM_MODE_OBJECT_PLANE,"type",&type) && type == DRM_PLANE_TYPE_PRIMARY)
            plane_id = p->plane_id;
        drmModeFreePlane(p);
        if (plane_id) break;
    }
    drmModeFreePlaneResources(planes);
    return plane_id ? 0 : -1;
}

static int surface_create(struct surface *s, const char *asset) {
    struct drm_mode_create_dumb c = {.width=1440,.height=3120,.bpp=32};
    if (drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &c)) return -1;
    s->handle=c.handle; s->size=c.size; s->pitch=c.pitch;
    uint32_t handles[4]={c.handle}, pitches[4]={c.pitch}, offsets[4]={0};
    if (drmModeAddFB2(fd,1440,3120,DRM_FORMAT_XRGB8888,handles,pitches,offsets,&s->fb,0)) return -1;
    struct drm_mode_map_dumb map = {.handle=c.handle};
    if (drmIoctl(fd,DRM_IOCTL_MODE_MAP_DUMB,&map)) return -1;
    s->map=mmap(NULL,c.size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,map.offset);
    if (s->map == MAP_FAILED) return -1;
    FILE *in=fopen(asset,"rb");
    if (!in) return -1;
    for (int y=0; y<3120; y++) {
        if (fread((char *)s->map+y*c.pitch,1,1440*4,in) != 1440*4) { fclose(in); return -1; }
    }
    int extra=fgetc(in); fclose(in);
    return extra == EOF ? 0 : -1;
}

static int show(uint32_t fb, drmModeModeInfo *mode, int initial) {
    drmModeAtomicReq *r=drmModeAtomicAlloc();
    uint32_t blob=0;
    int rc=-1;
    if (!r) return -1;
    if (initial) {
        if (drmModeCreatePropertyBlob(fd,mode,sizeof(*mode),&blob)) goto out;
        if (add(r,connector_id,DRM_MODE_OBJECT_CONNECTOR,"CRTC_ID",crtc_id) ||
            add(r,crtc_id,DRM_MODE_OBJECT_CRTC,"MODE_ID",blob) ||
            add(r,crtc_id,DRM_MODE_OBJECT_CRTC,"ACTIVE",1)) goto out;
    }
    if (add(r,plane_id,DRM_MODE_OBJECT_PLANE,"FB_ID",fb) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"CRTC_ID",crtc_id) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"SRC_X",0) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"SRC_Y",0) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"SRC_W",1440u<<16) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"SRC_H",3120u<<16) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"CRTC_X",0) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"CRTC_Y",0) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"CRTC_W",1440) ||
        add(r,plane_id,DRM_MODE_OBJECT_PLANE,"CRTC_H",3120)) goto out;
    rc=drmModeAtomicCommit(fd,r,initial ? DRM_MODE_ATOMIC_ALLOW_MODESET : 0,NULL);
out:
    if (rc) fprintf(stderr,"Atomic menu update: %s\n",strerror(errno));
    if (blob) drmModeDestroyPropertyBlob(fd,blob);
    drmModeAtomicFree(r);
    return rc;
}

static void syswrite(const char *path, const char *value) {
    int f=open(path,O_WRONLY); if (f>=0) { if (write(f,value,strlen(value))<0) perror(path); close(f); }
}

int main(int argc,char **argv) {
    if (argc==2 && !strcmp(argv[1],"--selftest")) return selftest();
    const char *assets=argc>1 ? argv[1] : "/usr/share/etherpocket/bootmenu";
    int timeout=argc>2 ? atoi(argv[2]) : 0;
    struct selection selection={0};
    if (argc>3 && !strcmp(argv[3],"1")) selection.selected=1;
    struct surface surfaces[2]={{0}};
    for (int i=0;i<20;i++) { fd=open("/dev/dri/card0",O_RDWR|O_CLOEXEC); if (fd>=0) break; sleep(1); }
    if (fd<0 || drmSetClientCap(fd,DRM_CLIENT_CAP_UNIVERSAL_PLANES,1) ||
        drmSetClientCap(fd,DRM_CLIENT_CAP_ATOMIC,1) || drmSetMaster(fd)) { perror("DRM master"); return 2; }
    drmModeModeInfo mode;
    if (find_panel(&mode)) { fprintf(stderr,"Native GM1920 DSI panel not available\n"); return 2; }
    for (int i=0;i<2;i++) {
        char path[512]; snprintf(path,sizeof(path),"%s/option-%d.xrgb",assets,i);
        if (surface_create(&surfaces[i],path)) { perror("menu asset framebuffer"); return 2; }
    }
    if (show(surfaces[selection.selected].fb,&mode,1)) return 2;
    syswrite("/sys/class/backlight/panel0-backlight/bl_power","0\n");
    syswrite("/sys/class/backlight/panel0-backlight/brightness","300\n");
    struct pollfd keys[32]; int n=0;
    for (int i=0;i<32;i++) {
        char path[64],name[128]={0}; snprintf(path,sizeof(path),"/dev/input/event%d",i);
        int f=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC); if (f<0) continue;
        ioctl(f,EVIOCGNAME(sizeof(name)),name);
        if (strcmp(name,"gpio-keys") && strcmp(name,"qpnp_pon")) { close(f); continue; }
        unsigned char bits[KEY_MAX/8+1]={0};
        if (ioctl(f,EVIOCGKEY(sizeof(bits)),bits)>=0 && (bits[KEY_POWER/8] & (1u<<(KEY_POWER%8)))) selection.ignore_power=1;
        keys[n++]=(struct pollfd){.fd=f,.events=POLLIN};
        fprintf(stderr,"Menu keys: %s %s\n",path,name);
    }
    if (n<2) { fprintf(stderr,"Power/volume input devices incomplete\n"); return 2; }
    time_t started=time(NULL);
    int result=124;
    for (;;) {
        if (timeout>0 && time(NULL)-started>=timeout) break;
        if (poll(keys,n,250)<0) { if (errno==EINTR) continue; break; }
        for (int i=0;i<n;i++) {
            if (!(keys[i].revents&POLLIN)) continue;
            struct input_event e;
            while (read(keys[i].fd,&e,sizeof(e))==sizeof(e)) {
                if (e.type!=EV_KEY) continue;
                int action=key(&selection,e.code,e.value);
                if (action==1) {
                    if (show(surfaces[selection.selected].fb,&mode,0)) { result=2; goto done; }
                    fprintf(stderr,"Selected: %s\n",selection.selected ? "Android 10" : "etherPocket");
                }
                if (action==2) { result=selection.selected ? 10 : 0; goto done; }
            }
        }
    }
done:
    fprintf(stderr,"Boot-menu result=%d\n",result);
    for (int i=0;i<n;i++) close(keys[i].fd);
    for (int i=0;i<2;i++) {
        if (surfaces[i].map) munmap(surfaces[i].map,surfaces[i].size);
        if (surfaces[i].fb) drmModeRmFB(fd,surfaces[i].fb);
        struct drm_mode_destroy_dumb d={.handle=surfaces[i].handle};
        drmIoctl(fd,DRM_IOCTL_MODE_DESTROY_DUMB,&d);
    }
    drmDropMaster(fd); close(fd);
    return result;
}
