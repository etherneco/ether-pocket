#!/bin/bash
# Build the Debian modesetting module against the matching ARM64 Xorg SDK.
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
source=/opt/etherpocket/xorg-source/xorg-server-21.1.16/hw/xfree86/drivers/modesetting
target=/opt/etherpocket/xorg-driver-rampatch
mkdir -p "$target" "$workspace/xorg/patches"
cp "$source/"*.c "$source/"*.h "$target/"
python3 - "$target/drmmode_display.c" "$workspace/xorg/patches/0001-skip-uninitialized-output-atoms.patch" <<'PY'
from pathlib import Path
import difflib, os, sys
p = Path(sys.argv[1])
before = p.read_text()
old = '        if (p->atoms[0] != property)\n'
new = ('        /* Unsupported DRM property types have no RandR atom array. */\n'
       '        if (!p->atoms || p->num_atoms < 1)\n'
       '            continue;\n\n' + old)
if before.count(old) != 1:
    raise SystemExit('Expected unique output-property setter context')
after = before.replace(old, new)
p.write_text(after)
Path(sys.argv[2]).write_text(''.join(difflib.unified_diff(
    before.splitlines(keepends=True), after.splitlines(keepends=True),
    fromfile='a/hw/xfree86/drivers/modesetting/drmmode_display.c',
    tofile='b/hw/xfree86/drivers/modesetting/drmmode_display.c')))
before_refresh = after
anchor = '    kmode->name[DRM_DISPLAY_MODE_LEN - 1] = 0;\n'
refresh = '''
    /* Qualcomm DSC modes require their advertised nominal refresh.
     * Timing-derived refresh differs because of command-mode blanking.
     * Preserve it only for an exact advertised name/timing match. */
    xf86CrtcConfigPtr config = XF86_CRTC_CONFIG_PTR(scrn);
    for (int o = 0; o < config->num_output; o++) {
        drmmode_output_private_ptr priv = config->output[o]->driver_private;
        if (!priv || !priv->mode_output)
            continue;
        for (int m = 0; m < priv->mode_output->count_modes; m++) {
            drmModeModeInfo *known = &priv->mode_output->modes[m];
            if ((!kmode->name[0] || !strcmp(kmode->name, known->name)) &&
                kmode->clock == known->clock &&
                kmode->hdisplay == known->hdisplay &&
                kmode->hsync_start == known->hsync_start &&
                kmode->hsync_end == known->hsync_end &&
                kmode->htotal == known->htotal &&
                kmode->vdisplay == known->vdisplay &&
                kmode->vsync_start == known->vsync_start &&
                kmode->vsync_end == known->vsync_end &&
                kmode->vtotal == known->vtotal) {
                kmode->vrefresh = known->vrefresh;
                if (!kmode->name[0]) {
                    strncpy(kmode->name, known->name, DRM_DISPLAY_MODE_LEN - 1);
                    kmode->name[DRM_DISPLAY_MODE_LEN - 1] = 0;
                }
                xf86DrvMsg(scrn->scrnIndex, X_INFO,
                           "EtherPocket advertised refresh: %s %u Hz\\n",
                           kmode->name, kmode->vrefresh);
                return;
            }
        }
    }
    xf86DrvMsg(scrn->scrnIndex, X_WARNING,
               "EtherPocket no exact advertised timing match: %s\\n", kmode->name);
'''
if after.count(anchor) != 1:
    raise SystemExit('Expected unique KMS mode conversion context')
after = after.replace(anchor, anchor + refresh)
p.write_text(after)
Path(sys.argv[2]).with_name('0002-preserve-advertised-mode-refresh.patch').write_text(
    ''.join(difflib.unified_diff(before_refresh.splitlines(keepends=True),
                                after.splitlines(keepends=True),
                                fromfile='a/hw/xfree86/drivers/modesetting/drmmode_display.c',
                                tofile='b/hw/xfree86/drivers/modesetting/drmmode_display.c')))
# Enabling scanout reached a Qualcomm 900E crash on this board. Keep the
# ordinary build limited to the independently verified property crash fix.
if os.environ.get('ETHERPOCKET_PANEL_REFRESH_TEST') != '1':
    p.write_text(before_refresh)
    print('Panel refresh test disabled; kernel crash must be investigated first.')
else:
    driver = p.with_name('driver.c')
    driver_before = driver.read_text()
    anchor = '        free(clip);\n        DamageEmpty(damage);\n'
    replacement = '''        /* Command-mode downstream DSI needs a commit after CPU damage.
         * Its framebuffer has no working DIRTYFB callback. Re-submit the
         * active plane through the existing atomic flip helper. */
        if (ms->atomic_modeset && ms->drmmode.shadow_enable && crtc->enabled &&
            (ret == -EINVAL || ret == -ENOSYS))
            ret = drmmode_crtc_flip(crtc, fb_id, 0, NULL);

        free(clip);
        if (ret == 0)
            DamageEmpty(damage);
'''
    if driver_before.count(anchor) != 1:
        raise SystemExit('Expected unique dirty framebuffer dispatch context')
    driver_after = driver_before.replace(anchor, replacement)
    # At fresh boot inactive CRTCs have no framebuffer; probing them used
    # to disable the shared damage tracker before the first real modeset.
    inactive = '        if (!drmmode_crtc)\n            continue;\n'
    dirty_start = driver_after.index('static void\ndispatch_dirty(ScreenPtr')
    dirty_end = driver_after.index('static void\ndispatch_dirty_pixmap', dirty_start)
    dirty_function = driver_after[dirty_start:dirty_end]
    if dirty_function.count(inactive) != 1:
        raise SystemExit('Expected unique CRTC dirty-dispatch guard')
    dirty_function = dirty_function.replace(inactive,
        '        if (!drmmode_crtc || !crtc->enabled)\n            continue;\n')
    driver_after = driver_after[:dirty_start] + dirty_function + driver_after[dirty_end:]
    disable = '        if (ret == -EINVAL || ret == -ENOSYS) {\n            ms->dirty_enabled = FALSE;'
    if driver_after.count(disable) != 1:
        raise SystemExit('Expected unique damage-disable guard')
    driver_after = driver_after.replace(disable,
        '        if ((ret == -EINVAL || ret == -ENOSYS) &&\n'
        '            !(ms->atomic_modeset && ms->drmmode.shadow_enable)) {\n'
        '            ms->dirty_enabled = FALSE;')
    init = '    if (err != -EINVAL && err != -ENOSYS) {\n'
    if driver_after.count(init) != 1:
        raise SystemExit('Expected unique damage initialization guard')
    driver_after = driver_after.replace(init,
        '    if ((ms->atomic_modeset && ms->drmmode.shadow_enable) ||\n'
        '        (err != -EINVAL && err != -ENOSYS)) {\n')
    driver.write_text(driver_after)
    Path(sys.argv[2]).with_name('0003-atomic-refresh-after-shadow-damage.patch').write_text(
        ''.join(difflib.unified_diff(driver_before.splitlines(keepends=True),
                                    driver_after.splitlines(keepends=True),
                                    fromfile='a/hw/xfree86/drivers/modesetting/driver.c',
                                    tofile='b/hw/xfree86/drivers/modesetting/driver.c')))
PY
# The driver is built as an external module using Debian's installed SDK
# configuration rather than generating the whole X server's private config.
printf '#include <xorg-server.h>\n' > "$target/xorg-config.h"
cat > "$target/dix-config.h" <<'EOF'
#ifndef _DIX_CONFIG_H_
#define _DIX_CONFIG_H_
#include <xorg-server.h>
#define HAVE_POLL 1
#define CONFIG_UDEV 1
#define CONFIG_UDEV_KMS 1
#define GLAMOR_HAS_GBM 1
#define GLAMOR_HAS_GBM_LINEAR 1
#define GBM_BO_WITH_MODIFIERS 1
#endif
EOF
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
read -ra cflags <<< "$(pkg-config --cflags xorg-server libdrm libudev gbm pixman-1 pciaccess)"
read -ra libs <<< "$(pkg-config --libs libdrm libudev gbm pixman-1 pciaccess)"
cd "$target"
aarch64-linux-gnu-gcc-12 -shared -fPIC -O2 -g -D_GNU_SOURCE \
  -DHAVE_DIX_CONFIG_H -DHAVE_LIBUDEV -include /usr/include/xorg/xorg-server.h \
  -I"$target" "${cflags[@]}" \
  dri2.c driver.c drmmode_display.c dumb_bo.c pageflip.c present.c vblank.c \
  -o "$workspace/build/modesetting_drv-fixed.so" "${libs[@]}"
sha256sum "$workspace/build/modesetting_drv-fixed.so"
