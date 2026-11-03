"""Apply the DSI-only backlight guard identified by the GM1920 DP Oops."""
from pathlib import Path
import difflib

root = Path('/opt/etherpocket/kernel')
name = 'drivers/gpu/drm/msm/sde/sde_connector.c'
path = root / name
before = path.read_text()
start = before.index('static int _sde_connector_update_bl_scale(')
end = before.index('//xiaoxiaohuan@OnePlus.MultiMediaService', start)
function = before[start:end]
needle = '\tdsi_display = c_conn->display;\n\tif (!dsi_display || !dsi_display->panel) {'
replacement = '''\t/* DP/virtual connectors do not carry a struct dsi_display. */
\tif (c_conn->base.connector_type != DRM_MODE_CONNECTOR_DSI)
\t\treturn 0;

\tdsi_display = c_conn->display;
\tif (!dsi_display || !dsi_display->panel) {'''
if function.count(needle) != 1 or 'DP/virtual connectors' in function:
    raise SystemExit('Unexpected or already-patched backlight function')
after = before[:start] + function.replace(needle, replacement) + before[end:]
path.write_text(after)
Path('/mnt/c/projects.local/mobiam/kernel/patches/0006-dsi-only-backlight-scale.patch').write_text(
    ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                               fromfile='a/'+name, tofile='b/'+name)))
print('Guarded DSI panel cast against DP/virtual connectors.')
