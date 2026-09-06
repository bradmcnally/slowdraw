#include "slow_draw/Renderer.h"
#include "slow_draw/Random.h"
#include <algorithm>
#include <cmath>
#include <cstdio>

namespace slow_draw { namespace {
constexpr int GW=240, GH=124, GRID_CONTENT_H=120, SCALE=4;
constexpr uint8_t LIGHT=15, DARK=0;
constexpr int BAYER[4][4]={{0,8,2,10},{12,4,14,6},{3,11,1,9},{15,7,13,5}};
constexpr int PIXEL_SIZES[]={8,10,10,10,10,12};
uint8_t px[GW*GH];
void clear(uint8_t s=LIGHT){std::fill_n(px,GW*GH,s);}
void dot(int x,int y,uint8_t s){if(x>=0&&x<GW&&y>=0&&y<GH)px[y*GW+x]=s&15;}
uint8_t get(int x,int y){return(x>=0&&x<GW&&y>=0&&y<GH)?px[y*GW+x]:LIGHT;}
void rect(int x,int y,int w,int h,uint8_t s){for(int yy=std::max(0,y);yy<std::min(GH,y+h);++yy)for(int xx=std::max(0,x);xx<std::min(GW,x+w);++xx)dot(xx,yy,s);}
void line(int x0,int y0,int x1,int y1,uint8_t s){int dx=abs(x1-x0),sx=x0<x1?1:-1,dy=-abs(y1-y0),sy=y0<y1?1:-1,e=dx+dy;for(;;){dot(x0,y0,s);if(x0==x1&&y0==y1)break;int e2=2*e;if(e2>=dy){e+=dy;x0+=sx;}if(e2<=dx){e+=dx;y0+=sy;}}}
void dither(int x,int y,int w,int h,uint8_t s){for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)dot(xx,yy,BAYER[yy&3][xx&3]<s?LIGHT:DARK);}
void frame(int x,int y,int w,int h,int t,uint8_t s){rect(x,y,w,t,s);rect(x,y+h-t,w,t,s);rect(x,y,t,h,s);rect(x+w-t,y,t,h,s);}

void loom(Random&r){clear(r.range(12,16));int cell=r.range(5,9),phase=r.range(0,cell);for(int y=-cell;y<GH+cell;y+=cell)for(int x=-cell;x<GW+cell;x+=cell){float f=sinf((x+phase)*.045f)+cosf(y*.071f)+sinf((x+y)*.024f);int s=std::max(1,std::min(14,int(8+f*3))),m=(x/cell+y/cell+r.range(0,3))%5;if(m==0){rect(x+2,y,1,cell,s);rect(x,y+2,cell,1,s);}else if(m==1){frame(x+1,y+1,cell-2,cell-2,1,s);dot(x+cell/2,y+cell/2,s/2);}else if(m==2){line(x+1,y+1,x+cell-2,y+cell-2,s);line(x+cell-2,y+1,x+1,y+cell-2,s);}else if(m==3&&f>-.2f)rect(x+1,y+1,cell-2,cell-2,s);}dither(r.range(35,170),r.range(20,78),r.range(22,55),r.range(16,42),r.range(10,15));}
void blocks(Random&r){clear(r.chance(.55f)?DARK:LIGHT);bool inv=get(0,0)==DARK;uint8_t fg=inv?LIGHT:DARK;for(int i=0;i<r.range(12,22);++i){int x=r.range(-20,220),y=r.range(-16,116),w=r.range(18,72),h=r.range(10,42),m=r.range(0,5);if(m==0)dither(x,y,w,h,r.range(3,14));else if(m==1)for(int yy=y;yy<y+h;yy+=4)for(int xx=x;xx<x+w;xx+=4)rect(xx,yy,2,2,fg);else if(m==2)for(int yy=y;yy<y+h;yy+=5)line(x,yy,x+w,yy,fg);else if(m==3)for(int yy=y;yy<y+h;yy+=6)for(int xx=x;xx<x+w;xx+=6){rect(xx,yy,1,5,fg);rect(xx-2,yy+2,5,1,fg);}else frame(x,y,w,h,r.range(1,3),fg);}}
void cluster(Random&r,bool){
  clear(LIGHT);
  struct Cell{int x,y;}; Cell cells[256];
  const int unit=PIXEL_SIZES[r.range(0,6)], cols=GW/unit, rows=GRID_CONTENT_H/unit;
  int count=1; cells[0]={r.range(7,std::max(8,cols-7)),r.range(5,std::max(6,rows-5))};
  const int steps=r.range(110,221);
  static const int dx[]={1,-1,0,0,1,-1},dy[]={0,0,1,-1,1,-1};
  for(int i=0;i<steps&&count<256;++i){
    Cell base=cells[r.range(0,count)]; int d=r.range(0,6); Cell next={base.x+dx[d],base.y+dy[d]};
    if(next.x<1||next.x>=cols-1||next.y<1||next.y>=rows-1)continue;
    bool exists=false;for(int j=0;j<count;++j)if(cells[j].x==next.x&&cells[j].y==next.y){exists=true;break;}
    if(!exists)cells[count++]=next;
  }
  float cx=0,cy=0;for(int i=0;i<count;++i){cx+=cells[i].x;cy+=cells[i].y;}cx/=count;cy/=count;
  for(int i=0;i<count;++i){float angle=atan2f(cells[i].y-cy,cells[i].x-cx),radius=hypotf(cells[i].x-cx,cells[i].y-cy);int shade=std::max(0,std::min(14,int(lroundf(7+5*sinf(angle*2.3f+radius*.7f)))));rect(cells[i].x*unit,cells[i].y*unit,unit,unit,shade);}
  for(int i=0;i<r.range(3,9);++i){Cell echo=cells[r.range(0,count)];echo.x+=r.chance(.5f)?-3:3;echo.y+=r.chance(.5f)?-3:3;if(echo.x>=0&&echo.x<cols&&echo.y>=0&&echo.y<rows)rect(echo.x*unit,echo.y*unit,unit,unit,r.range(3,13));}
}
void pixelField(Random&r){
  clear(LIGHT);
  struct Focus{float x,y,radius,weight;}; Focus focus[5];
  int focusCount=r.range(3,6);
  for(int i=0;i<focusCount;++i)focus[i]={float(r.range(0,GW)),float(r.range(0,GRID_CONTENT_H)),float(r.range(28,65)),r.chance(.55f)?1.0f:-1.0f};
  // Favor the large, even squares that read best on the physical panel.
  int unit=PIXEL_SIZES[r.range(0,6)];
  const int safeHeight=(GRID_CONTENT_H/unit)*unit;
  const float baseDensity=.38f+r.unit()*.10f;
  const float fieldStrength=.22f+r.unit()*.08f;
  const float rhythmStrength=.08f+r.unit()*.05f;
  for(int y=0;y<safeHeight;y+=unit)for(int x=0;x<GW;x+=unit){
    float field=0;for(int i=0;i<focusCount;++i){float dx=x-focus[i].x,dy=y-focus[i].y,s=focus[i].radius;field+=focus[i].weight*expf(-(dx*dx+dy*dy)/(2*s*s));}
    float presence=baseDensity+fieldStrength*field+rhythmStrength*sinf(x*.055f+y*.037f);
    if(r.unit()>std::max(.08f,std::min(.80f,presence)))continue;
    // Keep tones separated enough to remain legible after an e-paper refresh.
    int shade=std::max(2,std::min(13,int(lroundf(8.0f-field*4.5f+sinf((x-y)*.025f)*1.5f))));
    rect(x,y,unit,unit,shade);
  }
}
void subdivision(Random&r){
  clear(LIGHT);
  const int macro=PIXEL_SIZES[r.range(0,6)],sub=2;
  const int cols=GW/macro,rows=GRID_CONTENT_H/macro,cells=macro/sub;
  struct Focus{float x,y,radius,weight;}; Focus focus[5];
  const int focusCount=r.range(3,6);
  for(int i=0;i<focusCount;++i)focus[i]={float(r.range(0,cols)),float(r.range(0,rows)),float(r.range(3,8)),r.chance(.58f)?1.0f:-1.0f};
  static const int languages[]={0,2,3};
  const int language=languages[r.range(0,3)],phase=r.range(0,6);
  const uint8_t dark=static_cast<uint8_t>(r.range(0,5));
  const uint8_t mid=static_cast<uint8_t>(r.range(7,13));
  for(int gy=0;gy<rows;++gy)for(int gx=0;gx<cols;++gx){
    float field=0;
    for(int i=0;i<focusCount;++i){
      const float dx=gx-focus[i].x,dy=gy-focus[i].y,s=focus[i].radius;
      field+=focus[i].weight*expf(-(dx*dx+dy*dy)/(2*s*s));
    }
    const float rhythm=.12f*sinf(gx*.73f+gy*.41f+phase);
    const float presence=std::max(.10f,std::min(.86f,.43f+field*.24f+rhythm));
    if(r.unit()>presence)continue;
    const bool dense=field>.55f&&r.chance(.28f);
    const bool flip=((gx+gy+phase)&1)!=0;
    for(int sy=0;sy<cells;++sy)for(int sx=0;sx<cells;++sx){
      bool on=dense;
      if(!on&&language==0){
        // Alternating pixels join across neighboring macro-cells as a weave.
        on=((sx+sy+gx+gy+phase)&1)==0;
      }else if(!on&&language==1){
        // Open windows with a changing doorway in each tile.
        const bool edge=sx==0||sy==0||sx==cells-1||sy==cells-1;
        const bool doorway=flip?(sx==cells/2):(sy==cells/2);
        on=edge&&!doorway;
      }else if(!on&&language==2){
        // Diagonal bands reverse direction from tile to tile.
        const int diagonal=flip?sx+sy:sx+(cells-1-sy);
        on=((diagonal+phase)%3)==0;
      }else if(!on&&language==3){
        // A central knot connected to four corner points.
        const bool center=(sx==cells/2&&sy==cells/2);
        const bool corner=(sx==0||sx==cells-1)&&(sy==0||sy==cells-1);
        const bool arm=(sx==cells/2||sy==cells/2)&&((sx+sy+phase)&1)==0;
        on=center||corner||arm;
      }
      if(on){
        const uint8_t tone=((sx+2*sy+gx+phase)%5==0)?mid:dark;
        rect(gx*macro+sx*sub,gy*macro+sy*sub,sub,sub,tone);
      }
    }
  }
}
void mirroredLattice(Random&r){
  clear(LIGHT);
  const int unit=PIXEL_SIZES[r.range(0,6)];
  const int cols=GW/unit, rows=GRID_CONTENT_H/unit;
  const int halfCols=(cols+1)/2, halfRows=(rows+1)/2;
  auto place=[&](int x,int y,uint8_t shade){
    const int mx=cols-1-x, my=rows-1-y;
    rect(x*unit,y*unit,unit,unit,shade);
    rect(mx*unit,y*unit,unit,unit,shade);
    rect(x*unit,my*unit,unit,unit,shade);
    rect(mx*unit,my*unit,unit,unit,shade);
  };
  auto offset=[&](int dx,int dy,uint8_t shade){
    const int x=halfCols-1-dx,y=halfRows-1-dy;
    if(x>=0&&y>=0)place(x,y,shade);
  };

  const uint8_t dark=static_cast<uint8_t>(r.range(1,5));
  const uint8_t mid=static_cast<uint8_t>(r.range(7,12));
  if(r.chance(.55f)){
    // Construct an emblem from a core, measured rings, arms and satellites.
    const bool hollowCore=r.chance(.45f);
    if(!hollowCore)offset(0,0,dark);
    const int ringCount=r.range(1,3);
    for(int ring=1;ring<=ringCount;++ring){
      for(int p=0;p<=ring;++p){
        if(p==0||p==ring||((p+ring)&1)==0){
          offset(ring,p,ring==1?dark:mid);
          offset(p,ring,ring==1?dark:mid);
        }
      }
    }
    const int armX=r.range(ringCount+2,std::max(ringCount+3,halfCols-1));
    const int armY=r.range(ringCount+2,std::max(ringCount+3,halfRows-1));
    for(int d=ringCount+1;d<=armX;++d)if(d==armX||((d-ringCount)&1))offset(d,0,d==armX?dark:mid);
    for(int d=ringCount+1;d<=armY;++d)if(d==armY||((d-ringCount)&1))offset(0,d,d==armY?dark:mid);
    if(halfCols>4&&halfRows>4){
      const int satellites=r.range(1,4);
      for(int i=0;i<satellites;++i){
        const int dx=r.range(ringCount+1,halfCols);
        const int dy=r.range(ringCount+1,halfRows);
        offset(dx,dy,i==0?dark:mid);
      }
    }
  }else{
    // Repeat one geometric rule so small motifs combine into a larger weave.
    const int tileW=r.range(3,6),tileH=r.range(3,6),style=r.range(0,3);
    for(int y=0;y<halfRows;++y)for(int x=0;x<halfCols;++x){
      const int lx=x%tileW,ly=y%tileH;
      bool on=false;
      if(style==0){
        const int cx=tileW/2,cy=tileH/2;
        on=(lx==cx&&std::abs(ly-cy)<=1)||(ly==cy&&std::abs(lx-cx)<=1);
      }else if(style==1){
        on=(lx==0||lx==tileW-1)&&(ly==0||ly==tileH-1);
        on=on||((lx==tileW/2)&&(ly==tileH/2));
      }else{
        on=(lx==ly)||((lx+ly)==std::min(tileW,tileH)-1);
        on=on&&(lx<std::min(tileW,tileH)&&ly<std::min(tileW,tileH));
      }
      if(on){
        const int tileParity=((x/tileW)+(y/tileH))&1;
        place(x,y,tileParity?mid:dark);
      }
    }
  }
}
void strata(Random&r){clear(r.range(13,16));int start=r.range(12,42),step=r.range(4,8);for(int y=start;y<GH-4;y+=step){int x=r.range(3,18),end=GW-r.range(3,18);while(x<end){int run=r.range(3,16),shift=int(7*sinf(x*.055f+y*.09f));uint8_t s=r.range(0,16);if(r.unit()<float(y-start)/float(GH-start))rect(x,y+shift/3,std::min(run,end-x),r.range(1,4),s);else if((x/run+y/step)&1)rect(x,y,std::min(run,end-x),1,r.range(0,7));x+=run+r.range(0,5);}}int cuts=r.range(2,5);for(int i=0;i<cuts;++i)dither(r.range(20,200),r.range(start,GH-18),r.range(12,45),r.range(7,25),r.range(4,14));}
void density(Random&r){clear(r.chance(.7f)?r.range(0,3):r.range(13,16));bool dark=get(0,0)<8;for(int y=2;y<GH-2;y+=3)for(int x=2;x<GW-2;x+=3){float f=sinf(x*.035f+r.unit()*.12f)+cosf(y*.061f)+sinf((x-y)*.018f);float p=.18f+.16f*(f+2);if(r.unit()<p){uint8_t s=dark?r.range(8,16):r.range(0,8);int mode=(x/3+y/3)%7;if(mode==0){dot(x-1,y,s);dot(x,y,s);dot(x+1,y,s);dot(x,y-1,s);dot(x,y+1,s);}else rect(x,y,r.chance(.08f)?2:1,r.chance(.08f)?2:1,s);}}for(int i=0;i<r.range(3,8);++i){int cx=r.range(15,225),cy=r.range(12,112),rw=r.range(12,38),rh=r.range(8,24);frame(cx-rw/2,cy-rh/2,rw,rh,1,dark?r.range(7,15):r.range(1,8));}}
uint16_t gray(uint8_t l){uint8_t v=l*17;return uint16_t(((v&0xF8)<<8)|((v&0xFC)<<3)|(v>>3));}
void paint(M5Canvas&c){c.fillScreen(gray(LIGHT));for(int y=0;y<GH;++y)for(int x=0;x<GW;++x)c.fillRect(x*SCALE,y*SCALE,SCALE,SCALE,gray(get(x,y)));}
} // namespace

PrintInfo makePrintInfo(int year,int month,int day,uint32_t variant){PrintInfo i{};uint32_t base=dateSeed(year,month,day,kGeneratorVersion);i.seed=variant?mix32(base^mix32(variant*0x9e3779b9u)):base;const uint32_t pick=mix32(i.seed^0x51f15e5du)%3u;i.system=pick==0?System::CellularAggregate:(pick==1?System::PixelField:System::Subdivision);std::snprintf(i.identity,sizeof(i.identity),"SLOW DRAW  %04d.%02d.%02d/%u",year,month,day,unsigned(variant));return i;}
const char* systemName(System s){if(s==System::CellularAggregate)return "CELLULAR AGGREGATE";if(s==System::PixelField)return "PIXEL FIELD";if(s==System::Subdivision)return "SUBDIVISION";return "MIRRORED LATTICE";}
void renderPrint(M5Canvas&c,const PrintInfo&i){Random r(i.seed);if(i.system==System::CellularAggregate)cluster(r,false);else if(i.system==System::PixelField)pixelField(r);else if(i.system==System::Subdivision)subdivision(r);else mirroredLattice(r);paint(c);c.fillRect(0,GRID_CONTENT_H*SCALE,kCanvasWidth,kCanvasHeight-GRID_CONTENT_H*SCALE,gray(LIGHT));c.setTextColor(gray(DARK),gray(LIGHT));c.setTextSize(2);const int labelY=(GRID_CONTENT_H*SCALE+kCanvasHeight)/2;char seedLabel[5];std::snprintf(seedLabel,sizeof(seedLabel),"%04X",unsigned(i.seed&0xFFFFu));c.setTextDatum(middle_left);c.drawString(i.identity,24,labelY);c.setTextDatum(middle_right);c.drawString(seedLabel,kCanvasWidth-24,labelY);}
} // namespace slow_draw
