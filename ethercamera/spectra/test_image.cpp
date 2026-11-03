#include "image.h"
#include <cassert>
#include <vector>
#include <algorithm>
int main(){
 std::vector<uint8_t> raw(5008*3000);double gain=0;
 auto fill=[&](uint16_t r,uint16_t g,uint16_t b){for(int y=0;y<3000;y++)for(int x=0;x<4000;x+=4){auto *p=raw.data()+y*5008+x/4*5;p[4]=0;for(int i=0;i<4;i++){uint16_t v=y%2?(i%2?b:g):(i%2?g:r);p[i]=v>>2;p[4]|=(v&3)<<(i*2);}}};
 fill(64,64,64);auto black=spectra::rgb(raw.data(),gain);assert(black.size()==640*480*3);for(auto c:black)assert(c==0);
 fill(1023,1023,1023);auto white=spectra::rgb(raw.data(),gain);for(auto c:white)assert(uint8_t(c)==255);
 gain=0;fill(65,68,72);auto low=spectra::rgb(raw.data(),gain);assert(uint8_t(low[0])<uint8_t(low[1])&&uint8_t(low[1])<uint8_t(low[2]));
 // Padding is not part of the MIPI image and must never become bright pixels.
 for(int y=0;y<3000;y++)std::fill(raw.begin()+y*5008+5000,raw.begin()+(y+1)*5008,255);
 gain=0;assert(spectra::rgb(raw.data(),gain)==low);
}
