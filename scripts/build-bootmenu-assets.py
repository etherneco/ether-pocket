"""Compose native-resolution boot-menu screens using the supplied logo unchanged."""
from pathlib import Path
import hashlib
import json
import shutil
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
asset = root/'assets/etherneco-logo-header.png'
asset.parent.mkdir(exist_ok=True)
if not asset.exists():
    raise SystemExit('Missing supplied logo: '+str(asset))
out = root/'build/bootmenu'
out.mkdir(parents=True,exist_ok=True)
logo = Image.open(asset).convert('RGBA')
# Keep the web PNG at its native size: no stretching or discarded alpha.
logo.thumbnail((1052,528),Image.Resampling.LANCZOS)
logo_position = ((1440-logo.width)//2,1164-logo.height//2)
font_dir = Path(r'C:\Windows\Fonts')
normal = ImageFont.truetype(str(font_dir/'segoeui.ttf'),66)
selected_font = ImageFont.truetype(str(font_dir/'segoeuib.ttf'),66)
small = ImageFont.truetype(str(font_dir/'segoeui.ttf'),36)
for selected in range(2):
    screen = Image.new('RGB',(1440,3120),'black')
    screen.paste(logo,logo_position,logo)
    draw = ImageDraw.Draw(screen)
    for index,label in enumerate(['etherPocket','Android 10']):
        top = 1540+index*210
        active = index == selected
        if active:
            draw.rounded_rectangle((200,top,1240,top+156),radius=28,fill='#061922',outline='#24c9eb',width=3)
        draw.text((720,top+78),label,font=selected_font if active else normal,
                  anchor='mm',fill='#ffffff' if active else '#8e9ba6')
    draw.text((720,2490),'Głośność + / −: wybór',font=small,anchor='mm',fill='#7d8d98')
    draw.text((720,2555),'Power: uruchom',font=small,anchor='mm',fill='#7d8d98')
    screen.save(out/('option-'+str(selected)+'.png'))
    (out/('option-'+str(selected)+'.xrgb')).write_bytes(screen.tobytes('raw','BGRX'))
shutil.copyfile(out/'option-0.png',out/'preview.png')
manifest = dict(width=1440,height=3120,stride=5760,format='DRM_FORMAT_XRGB8888',
                logo_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),
                logo_asset=asset.name,logo_size=list(logo.size),
                logo_position=list(logo_position),logo_alpha_composited=True,
                options=['etherPocket','Android 10'])
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Boot-menu assets created:',out)
