#include "image.h"
#include <cmath>
QByteArray spectra::rgb(const uint8_t *raw,double &gain){
 QByteArray out(640*480*3,Qt::Uninitialized);uint8_t gamma[1024];uint32_t histogram[1024]{};
 auto pixel=[&](int x,int y){const auto *p=raw+y*5008+(x/4)*5;return (uint16_t(p[x%4])<<2)|((p[4]>>((x%4)*2))&3);};
 // Meter actual sensor samples before gamma. Limit software lift to 16x;
 // black-level noise alone must not trigger a full-contrast fake scene.
 for(int y=0;y<3000;y+=24)for(int x=0;x<4000;x+=24)histogram[qMax(0,int(pixel(x+1,y))-64)]++;
 uint32_t total=0;for(auto n:histogram)total+=n;uint32_t count=0;int white=959;
 for(int i=0;i<1024;i++){count+=histogram[i];if(count>=total*0.995){white=i;break;}}
 const double target=white>2?qBound(1.,850./white,16.):1.;gain=gain==0?target:gain*0.8+target*0.2;
 for(int i=0;i<1024;i++)gamma[i]=uint8_t(std::pow(qMin(1.,qMax(0,i-64)*gain/959.),1/2.2)*255);
 for(int y=0;y<480;y++)for(int x=0;x<640;x++){
  int sx=(x*4000/640)&~1,sy=(y*3000/480)&~1;uint32_t r=0,g=0,b=0;
  // Average the sensor area represented by one preview pixel. Keeping only
  // one Bayer cell discards almost all available light samples and aliases.
  for(int dy=0;dy<6;dy+=2)for(int dx=0;dx<6;dx+=2){r+=pixel(sx+dx,sy+dy);g+=pixel(sx+dx+1,sy+dy)+pixel(sx+dx,sy+dy+1);b+=pixel(sx+dx+1,sy+dy+1);}
  auto *p=reinterpret_cast<uint8_t*>(out.data())+(y*640+x)*3;p[0]=gamma[r/9];p[1]=gamma[g/18];p[2]=gamma[b/9];
 }return out;
}
