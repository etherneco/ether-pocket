"""Generate code-drawn XFWM frame assets. No application/UI overlay is involved."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'build/qt-tooling'))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor,QImage,QPainter,QPainterPath,QPen,QLinearGradient

ROOT=Path(__file__).resolve().parent.parent/'ethershell/themes'
for dark in [False,True]:
    for desktop in [False,True]:
        h,b,r,grip=(52,44,14,48) if desktop else (152,132,32,144)
        name='EtherSurface-'+('Dark' if dark else 'Light')+('-Desktop' if desktop else '-Phone')
        out=ROOT/name/'xfwm4';out.mkdir(parents=True,exist_ok=True)
        for state in ['active','inactive']:
            top,bottom,ink,line=('#263e5c','#172c46','#edf5ff','#496887') if dark else ('#f8fbff','#dfecff','#122c50','#b9d3f3')
            if state=='inactive':top,bottom,ink=('#24344b','#1c2c42','#b0bfd0') if dark else ('#f3f6fb','#e7eef8','#657b96')
            def canvas(w,height):
                img=QImage(w,height,QImage.Format_ARGB32_Premultiplied);img.fill(Qt.transparent)
                p=QPainter(img);p.setRenderHint(QPainter.Antialiasing);return img,p
            def finish(img,p,file):p.end();assert img.save(str(out/file))
            def fill(p,rect):
                gradient=QLinearGradient(0,0,0,h);gradient.setColorAt(0,QColor(top));gradient.setColorAt(1,QColor(bottom));p.fillRect(rect,gradient)
            for i in range(1,6):
                img,p=canvas(2,h);fill(p,img.rect());p.fillRect(0,h-2,2,2,QColor(line));finish(img,p,f'title-{i}-{state}.png')
            for side in ['left','right']:
                img,p=canvas(r,h);path=QPainterPath();path.addRoundedRect(QRectF(0 if side=='left' else -r,0,2*r,2*h),r,r)
                p.setClipPath(path);fill(p,img.rect());p.setPen(QPen(QColor(line),2));p.drawLine(0,h-1,r,h-1);finish(img,p,f'top-{side}-{state}.png')
                img,p=canvas(4 if desktop else 6,2);p.fillRect(img.rect(),QColor(line));finish(img,p,f'{side}-{state}.png')
            img,p=canvas(2,grip);p.fillRect(img.rect(),QColor(bottom));p.fillRect(0,0,2,2,QColor(line));p.fillRect(0,grip-2,2,2,QColor(line));finish(img,p,f'bottom-{state}.png')
            img,p=canvas(r,grip);path=QPainterPath();path.addRoundedRect(QRectF(0,-grip,2*r,2*grip),r,r);p.setClipPath(path);p.fillRect(img.rect(),QColor(bottom));p.setPen(QPen(QColor(line),2));p.drawLine(0,grip-1,r,grip-1);finish(img,p,f'bottom-left-{state}.png')
            img,p=canvas(grip,grip);path=QPainterPath();path.addRoundedRect(QRectF(-grip,-grip,2*grip,2*grip),r,r);p.setClipPath(path);p.fillRect(img.rect(),QColor(bottom));p.setPen(QPen(QColor(line),2));p.drawLine(0,grip-1,grip,grip-1)
            p.setBrush(QColor('#284967' if dark else '#eff6ff'));p.drawRoundedRect(QRectF(5,5,grip-10,grip-10),r*.7,r*.7)
            p.setPen(QPen(QColor(ink),max(2,grip/40),Qt.SolidLine,Qt.RoundCap))
            for offset in [.22,.34,.46]:p.drawLine(int(grip*(1-offset)),int(grip*.72),int(grip*.72),int(grip*(1-offset)))
            finish(img,p,f'bottom-right-{state}.png')
            for button in ['menu','hide','maximize','close','shade','stick']:
                for effect in [state,'prelight','pressed']:
                    if state=='inactive' and effect!=state:continue
                    for toggled in ([False,True] if button in ['maximize','shade','stick'] else [False]):
                        img,p=canvas(b,b);bg=('#284967' if dark else '#eff6ff');fg=ink
                        if effect=='prelight':bg='#cfe4ff' if not dark else '#355a7d'
                        if effect=='pressed':bg,fg='#087cff','#ffffff'
                        if button=='close' and effect=='prelight':bg,fg='#b52e49','#ffffff'
                        p.setPen(QPen(QColor(line),2));p.setBrush(QColor(bg));p.drawRoundedRect(QRectF(2,2,b-4,b-4),r*.8,r*.8)
                        p.setPen(QPen(QColor(fg),max(2,b/26),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
                        lo,hi,mid=b*.34,b*.66,b*.5
                        if button=='close':p.drawLine(int(lo),int(lo),int(hi),int(hi));p.drawLine(int(hi),int(lo),int(lo),int(hi))
                        elif button=='hide':p.drawLine(int(lo),int(mid),int(hi),int(mid))
                        elif button=='maximize':
                            if toggled:p.drawRect(QRectF(lo+4,lo-4,hi-lo,hi-lo))
                            p.drawRect(QRectF(lo,lo,hi-lo,hi-lo))
                        elif button=='menu':
                            for yy in [.36,.5,.64]:p.drawLine(int(lo),int(b*yy),int(hi),int(b*yy))
                        elif button=='shade':p.drawLine(int(lo),int(hi),int(mid),int(lo));p.drawLine(int(mid),int(lo),int(hi),int(hi))
                        else:p.drawEllipse(QRectF(lo,lo,hi-lo,hi-lo))
                        suffix=('-toggled' if toggled else '')+'-'+effect
                        finish(img,p,button+suffix+'.png')
        (out/'themerc').write_text('''active_text_color=INK
inactive_text_color=MUTED
active_text_shadow_color=INK
inactive_text_shadow_color=MUTED
button_offset=8
button_spacing=8
full_width_title=true
frame_border_top=2
maximized_offset=4
show_app_icon=true
title_horizontal_offset=12
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_shadow_active=false
title_shadow_inactive=false
shadow_opacity=20
shadow_delta_x=-3
shadow_delta_y=-3
shadow_delta_width=4
shadow_delta_height=4
'''.replace('INK','#edf5ff' if dark else '#122c50').replace('MUTED','#b0bfd0' if dark else '#657b96'))
print('Generated four native XFWM themes in '+str(ROOT))
