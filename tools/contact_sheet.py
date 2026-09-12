#!/usr/bin/env python3
"""Generate Slow Draw contact sheets with only the Python standard library."""

from pathlib import Path
import argparse, math, random, subprocess

W, H = 240, 124
CONTENT_H = 120
PIXEL_SIZES = (8,10,10,10,10,12)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "studies"

def canvas(value=15): return [[value for _ in range(W)] for _ in range(H)]
class FirmwareRandom:
    def __init__(self, seed): self.state=seed&0xffffffff or 0x6d2b79f5
    def next(self):
        x=self.state; x^=(x<<13)&0xffffffff; x^=x>>17; x^=(x<<5)&0xffffffff
        self.state=x&0xffffffff; return self.state
    def range(self, low, high): return low+self.next()%(high-low)
    def unit(self): return (self.next()>>8)*(1.0/16777216.0)
    def chance(self, probability): return self.unit()<probability
def lround(value): return math.floor(value+.5) if value>=0 else math.ceil(value-.5)
def put(a,x,y,v):
    if 0 <= x < W and 0 <= y < H: a[y][x] = max(0,min(15,int(v)))
def block(a,x,y,w,h,v):
    for yy in range(max(0,y),min(H,y+h)):
        for xx in range(max(0,x),min(W,x+w)): put(a,xx,yy,v)
def line(a,x0,y0,x1,y1,v):
    dx=abs(x1-x0); sx=1 if x0<x1 else -1; dy=-abs(y1-y0); sy=1 if y0<y1 else -1; error=dx+dy
    while True:
        put(a,x0,y0,v)
        if x0==x1 and y0==y1: break
        twice=2*error
        if twice>=dy: error+=dy; x0+=sx
        if twice<=dx: error+=dx; y0+=sy
def write_pgm(a,path):
    height,width=len(a),len(a[0])
    with path.open("wb") as f:
        f.write(f"P5\n{width} {height}\n255\n".encode())
        f.write(bytes(v*17 for row in a for v in row))

def write_sheet(images,path):
    image_h,image_w=len(images[0]),len(images[0][0])
    scale=1 if image_w>W else 2
    gap,cols,rows=8,5,10
    sw=cols*image_w*scale+(cols+1)*gap; sh=rows*image_h*scale+(rows+1)*gap
    sheet=[[216 for _ in range(sw)] for _ in range(sh)]
    for i,a in enumerate(images):
        ox=gap+(i%cols)*(image_w*scale+gap); oy=gap+(i//cols)*(image_h*scale+gap)
        for y,row in enumerate(a):
            for x,v in enumerate(row):
                value=v*17
                for yy in range(scale):
                    for xx in range(scale): sheet[oy+y*scale+yy][ox+x*scale+xx]=value
    with path.open("wb") as f:
        f.write(f"P5\n{sw} {sh}\n255\n".encode())
        f.write(bytes(v for row in sheet for v in row))

def scanline_erosion(seed):
    r=random.Random(seed); a=canvas(r.choice([14,15])); step=r.choice([4,5,6]); phase=r.randrange(9)
    boundary=r.randint(28,70); slope=r.uniform(.16,.55); freq=r.uniform(.045,.085)
    for y in range(6,H-5,step):
        density=max(0,min(1,(y-boundary)/(H-boundary)))
        x=5
        while x<W-5:
            run=r.randint(4,14); wave=round(2*math.sin(x*freq+y*.09+phase))
            if y < boundary or r.random() < .42+density*.48:
                value=r.choice([0,1,2,4,7,10,13]) if density>.12 else r.choice([0,1,2])
                block(a,x,y+wave,run,r.choice([1,1,2]),value)
            x += run+r.randint(1,5)
    # A coherent dissolution edge rather than uniform noise.
    for y in range(boundary,H):
        edge=int(W*.5 + math.sin(y*.12+phase)*W*.32)
        for x in range(W):
            if abs(x-edge) < (y-boundary)*.32 and r.random()<.16:
                block(a,x,y,r.choice([1,2,3]),1,r.randrange(16))
    return a

def motif_field(seed):
    r=random.Random(seed); a=canvas(r.choice([1,2,13,14])); cell=r.choice([5,6,7,8]); ox=r.randrange(cell); oy=r.randrange(cell)
    centers=[(r.randrange(W),r.randrange(H),r.uniform(18,50),r.choice([-1,1])) for _ in range(r.randint(3,6))]
    for y in range(oy-cell,H,cell):
        for x in range(ox-cell,W,cell):
            field=sum(sign*math.exp(-((x-cx)**2+(y-cy)**2)/(2*s*s)) for cx,cy,s,sign in centers)
            value=max(0,min(15,round(8+field*11)))
            mode=(round(field*5)+r.randrange(3))%4
            if mode==0:
                block(a,x+cell//2,y+1,1,cell-2,value); block(a,x+1,y+cell//2,cell-2,1,value)
            elif mode==1:
                for i in range(1,cell-1): put(a,x+i,y+i,value); put(a,x+cell-1-i,y+i,value)
            elif mode==2:
                for xx,yy in ((1,1),(cell-2,1),(1,cell-2),(cell-2,cell-2)): put(a,x+xx,y+yy,value)
            else:
                for xx in range(1,cell-1): put(a,x+xx,y+1,value); put(a,x+xx,y+cell-2,value)
                for yy in range(1,cell-1): put(a,x+1,y+yy,value); put(a,x+cell-2,y+yy,value)
    return a

def dither_architecture(seed):
    r=random.Random(seed); inverse=r.random()<.45; a=canvas(1 if inverse else 15)
    bayer=((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5))
    regions=[]
    # Regions share edges and align to a coarse module.
    module=r.choice([6,8,10]); x=r.randrange(-2,3)*module
    while x<W:
        w=r.randint(2,7)*module; y=r.randint(-2,9)*module; h=r.randint(2,9)*module
        regions.append((x,y,w,h,r.randrange(1,15))); x+=r.randint(1,5)*module
    for _ in range(r.randint(7,14)):
        regions.append((r.randrange(-2,20)*module,r.randrange(-2,13)*module,r.randint(2,8)*module,r.randint(2,7)*module,r.randrange(1,15)))
    for x,y,w,h,tone in regions:
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                lo=max(0,tone-2); hi=min(15,tone+2)
                put(a,xx,yy,hi if bayer[yy&3][xx&3] < (tone&3)*4 else lo)
    return a

def single_cellular(r):
    a=canvas(15); unit=PIXEL_SIZES[r.range(0,6)]; cols=W//unit; rows=CONTENT_H//unit
    cells=[(r.range(7,max(8,cols-7)),r.range(5,max(6,rows-5)))]
    directions=((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1))
    for _ in range(r.range(110,221)):
        bx,by=cells[r.range(0,len(cells))]; dx,dy=directions[r.range(0,6)]
        nx,ny=bx+dx,by+dy
        if 1<=nx<cols-1 and 1<=ny<rows-1 and (nx,ny) not in cells: cells.append((nx,ny))
    cx=sum(x for x,y in cells)/len(cells); cy=sum(y for x,y in cells)/len(cells)
    for x,y in cells:
        angle=math.atan2(y-cy,x-cx); radius=math.hypot(x-cx,y-cy)
        value=max(0,min(14,lround(7+5*math.sin(angle*2.3+radius*.7))))
        block(a,x*unit,y*unit,unit,unit,value)
    for _ in range(r.range(3,9)):
        x,y=cells[r.range(0,len(cells))]; x+=-3 if r.chance(.5) else 3; y+=-3 if r.chance(.5) else 3
        if 0<=x<cols and 0<=y<rows: block(a,x*unit,y*unit,unit,unit,r.range(3,13))
    return a

def cellular_aggregate(seed):
    r=FirmwareRandom(seed)
    return dual_cellular_attractor(rng=r) if r.chance(.30) else single_cellular(r)

def dual_cellular(seed, interaction):
    r=FirmwareRandom(seed); a=canvas(15); unit=PIXEL_SIZES[r.range(0,6)]
    cols,rows=W//unit,CONTENT_H//unit
    margin_x=max(3,cols//6); margin_y=max(3,rows//5)
    cells=[[(r.range(margin_x,max(margin_x+1,cols//2-1)),r.range(margin_y,rows-margin_y))],
           [(r.range(cols//2+1,cols-margin_x),r.range(margin_y,rows-margin_y))]]
    directions=((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1))
    steps=r.range(150,261)
    for step in range(steps):
        owner=step&1; other=1-owner
        bx,by=cells[owner][r.range(0,len(cells[owner]))]
        dx,dy=directions[r.range(0,6)]; candidate=(bx+dx,by+dy)
        if not (1<=candidate[0]<cols-1 and 1<=candidate[1]<rows-1): continue
        if candidate in cells[owner]: continue
        if interaction=="boundary" and candidate in cells[other]: continue
        cells[owner].append(candidate)
    centers=[]
    for group in cells:
        centers.append((sum(x for x,y in group)/len(group),sum(y for x,y in group)/len(group)))
    occupancy={}
    for owner,group in enumerate(cells):
        cx,cy=centers[owner]
        for x,y in group:
            angle=math.atan2(y-cy,x-cx); radius=math.hypot(x-cx,y-cy)
            shade=max(1,min(13,lround(7+5*math.sin(angle*2.3+radius*.7+owner*1.7))))
            if (x,y) in occupancy:
                occupancy[(x,y)]=max(0,min(3,min(occupancy[(x,y)],shade)-2))
            else:
                occupancy[(x,y)]=shade
    if interaction=="boundary":
        left=set(cells[0]); right=set(cells[1])
        for x,y in left:
            if any((x+dx,y+dy) in right for dx,dy in directions[:4]): occupancy[(x,y)]=1
        for x,y in right:
            if any((x+dx,y+dy) in left for dx,dy in directions[:4]): occupancy[(x,y)]=1
    for (x,y),shade in occupancy.items(): block(a,x*unit,y*unit,unit,unit,shade)
    for owner in range(2):
        for _ in range(r.range(2,5)):
            x,y=cells[owner][r.range(0,len(cells[owner]))]
            x+=-3 if r.chance(.5) else 3; y+=-3 if r.chance(.5) else 3
            if 0<=x<cols and 0<=y<rows and (x,y) not in occupancy:
                block(a,x*unit,y*unit,unit,unit,r.range(4,12))
    return a

def dual_cellular_attractor(seed=None, rng=None):
    r=rng if rng is not None else FirmwareRandom(seed); a=canvas(15); unit=PIXEL_SIZES[r.range(0,6)]
    cols,rows=W//unit,CONTENT_H//unit
    attractor=(r.range(cols//3,cols-cols//3),r.range(rows//3,rows-rows//3))
    vertical=r.chance(.35)
    if vertical:
        starts=[(r.range(3,cols-3),r.range(1,max(2,rows//4))),
                (r.range(3,cols-3),r.range(rows-rows//4,rows-1))]
    else:
        starts=[(r.range(1,max(2,cols//4)),r.range(3,rows-3)),
                (r.range(cols-cols//4,cols-1),r.range(3,rows-3))]
    groups=[[starts[0]],[starts[1]]]; occupied=[{starts[0]},{starts[1]}]
    directions=((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1))
    touched=False
    for step in range(r.range(210,321)):
        owner=step&1; other=1-owner
        if not touched and r.chance(.72):
            sample=[groups[owner][r.range(0,len(groups[owner]))] for _ in range(min(8,len(groups[owner])))]
            bx,by=min(sample,key=lambda cell:(cell[0]-attractor[0])**2+(cell[1]-attractor[1])**2)
            candidates=[]
            for dx,dy in directions:
                nx,ny=bx+dx,by+dy
                if 1<=nx<cols-1 and 1<=ny<rows-1 and (nx,ny) not in occupied[owner]:
                    score=(nx-attractor[0])**2+(ny-attractor[1])**2+r.unit()*8
                    candidates.append((score,(nx,ny)))
            if not candidates: continue
            candidate=min(candidates)[1]
        else:
            bx,by=groups[owner][r.range(0,len(groups[owner]))]
            dx,dy=directions[r.range(0,6)]; candidate=(bx+dx,by+dy)
            if not (1<=candidate[0]<cols-1 and 1<=candidate[1]<rows-1): continue
            if candidate in occupied[owner]: continue
        if candidate in occupied[other]:
            touched=True
            continue
        groups[owner].append(candidate); occupied[owner].add(candidate)
        if any((candidate[0]+dx,candidate[1]+dy) in occupied[other] for dx,dy in directions[:4]):
            touched=True
    centers=[(sum(x for x,y in group)/len(group),sum(y for x,y in group)/len(group)) for group in groups]
    contact=set()
    for owner in range(2):
        other=1-owner
        for x,y in groups[owner]:
            if any((x+dx,y+dy) in occupied[other] for dx,dy in directions[:4]): contact.add((x,y))
    for owner,group in enumerate(groups):
        cx,cy=centers[owner]
        for x,y in group:
            angle=math.atan2(y-cy,x-cx); radius=math.hypot(x-cx,y-cy)
            shade=1 if (x,y) in contact else max(2,min(13,lround(7+5*math.sin(angle*2.3+radius*.7+owner*1.7))))
            block(a,x*unit,y*unit,unit,unit,shade)
    for _ in range(r.range(3,7)):
        owner=r.range(0,2); x,y=groups[owner][r.range(0,len(groups[owner]))]
        x+=-3 if r.chance(.5) else 3; y+=-3 if r.chance(.5) else 3
        if 0<=x<cols and 0<=y<rows and (x,y) not in occupied[0] and (x,y) not in occupied[1]:
            block(a,x*unit,y*unit,unit,unit,r.range(4,12))
    return a

def pixel_field(seed):
    r=FirmwareRandom(seed); a=canvas(15); count=r.range(3,6)
    centers=[(r.range(0,W),r.range(0,CONTENT_H),r.range(28,65),1 if r.chance(.55) else -1) for _ in range(count)]
    unit=PIXEL_SIZES[r.range(0,6)]; safe=(CONTENT_H//unit)*unit
    base=.38+r.unit()*.10; strength=.22+r.unit()*.08; rhythm=.08+r.unit()*.05
    for y in range(0,safe,unit):
        for x in range(0,W,unit):
            field=sum(weight*math.exp(-((x-cx)**2+(y-cy)**2)/(2*radius*radius)) for cx,cy,radius,weight in centers)
            presence=base+strength*field+rhythm*math.sin(x*.055+y*.037)
            if r.unit()>max(.08,min(.80,presence)): continue
            shade=max(2,min(13,lround(8-field*4.5+math.sin((x-y)*.025)*1.5)))
            block(a,x,y,unit,unit,shade)
    return a

def subdivision(seed, language=None):
    r=FirmwareRandom(seed); a=canvas(15); macro=PIXEL_SIZES[r.range(0,6)]; sub=2
    cols,rows,cells=W//macro,CONTENT_H//macro,macro//sub
    count=r.range(3,6)
    centers=[(r.range(0,cols),r.range(0,rows),r.range(3,8),1 if r.chance(.58) else -1) for _ in range(count)]
    languages=(0,2,3); selected=languages[r.range(0,3)]; language=selected if language is None else language
    phase=r.range(0,6); dark=r.range(0,5); mid=r.range(7,13)
    for gy in range(rows):
        for gx in range(cols):
            field=sum(sign*math.exp(-((gx-cx)**2+(gy-cy)**2)/(2*s*s)) for cx,cy,s,sign in centers)
            rhythm=.12*math.sin(gx*.73+gy*.41+phase)
            presence=max(.10,min(.86,.43+field*.24+rhythm))
            if r.unit()>presence: continue
            dense=field>.55 and r.chance(.28)
            flip=((gx+gy+phase)&1)!=0
            for sy in range(cells):
                for sx in range(cells):
                    on=dense
                    if not on and language==0:
                        on=((sx+sy+gx+gy+phase)&1)==0
                    elif not on and language==1:
                        edge=sx==0 or sy==0 or sx==cells-1 or sy==cells-1
                        doorway=(sx==cells//2) if flip else (sy==cells//2)
                        on=edge and not doorway
                    elif not on and language==2:
                        diagonal=(sx+sy) if flip else (sx+(cells-1-sy))
                        on=((diagonal+phase)%3)==0
                    elif not on and language==3:
                        center=sx==cells//2 and sy==cells//2
                        corner=(sx in (0,cells-1)) and (sy in (0,cells-1))
                        arm=(sx==cells//2 or sy==cells//2) and ((sx+sy+phase)&1)==0
                        on=center or corner or arm
                    if on:
                        tone=mid if (sx+2*sy+gx+phase)%5==0 else dark
                        block(a,gx*macro+sx*sub,gy*macro+sy*sub,sub,sub,tone)
    return a

def dither_pressure(seed, mode=None, pixel=1):
    r=FirmwareRandom(seed); a=canvas(15); count=r.range(3,6)
    centers=[(r.range(0,W),r.range(0,CONTENT_H),r.range(24,72),.34 if r.chance(.52) else -.34) for _ in range(count)]
    ax=.025+r.unit()*.035; ay=.035+r.unit()*.045; diagonal=.012+r.unit()*.025; phase=r.unit()*6.28318
    values=[]
    for y in range(120):
        row=[]
        for x in range(W):
            value=.57+.17*math.sin(x*ax+phase)+.13*math.cos(y*ay-phase*.7)+.09*math.sin((x+y)*diagonal)
            value+=sum(weight*math.exp(-((x-cx)**2+(y-cy)**2)/(2*radius*radius)) for cx,cy,radius,weight in centers)
            row.append(lround(max(0,min(1,value))*4096))
        values.append(row)
    bayer=((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5))
    coarse_w,coarse_h=W//pixel,120//pixel
    coarse=[]
    for gy in range(coarse_h):
        row=[]
        for gx in range(coarse_w):
            total=sum(values[y][x] for y in range(gy*pixel,(gy+1)*pixel) for x in range(gx*pixel,(gx+1)*pixel))
            row.append(total//(pixel*pixel))
        coarse.append(row)
    def coarse_pixel(x,y,value):
        block(a,x*pixel,y*pixel,pixel,pixel,value)
    selected=r.range(0,2); mode=selected if mode is None else mode
    if mode==0:
        ox,oy=r.range(0,4),r.range(0,4)
        for y in range(coarse_h):
            for x in range(coarse_w): coarse_pixel(x,y,15 if coarse[y][x]>(bayer[(y+oy)&3][(x+ox)&3]*2+1)*128 else 0)
    elif mode==1:
        for y in range(coarse_h):
            for x in range(coarse_w):
                old=coarse[y][x]; quantized=4096 if old>=2048 else 0; coarse_pixel(x,y,15 if quantized else 0); error=int((old-quantized)/8)
                for sx,sy in ((x+1,y),(x+2,y),(x-1,y+1),(x,y+1),(x+1,y+1),(x,y+2)):
                    if 0<=sx<coarse_w and 0<=sy<coarse_h: coarse[sy][sx]=max(-8192,min(12288,coarse[sy][sx]+error))
    return a

def murmuration(seed, diffusion=False, fine=False):
    r=FirmwareRandom(seed); a=canvas(15); topology=r.range(0,5)
    lobes=[]; cuts=[]
    def lobe(x,y,rx,ry,angle=0,weight=1): lobes.append((x,y,rx,ry,angle,weight))
    def cut(x,y,rx,ry,angle=0,weight=1): cuts.append((x,y,rx,ry,angle,weight))
    cx,cy=r.range(82,159),r.range(43,78); flip=-1 if r.chance(.5) else 1
    if topology==0:  # hooked comma, with a dense head and tapering tail
        lobe(cx,cy,48,28,0,1.25); angle=-flip*(.35+r.unit()*.35)
        for i in range(1,7):
            angle+=flip*(.16+r.unit()*.17); length=27-i*3
            x=cx+flip*i*25; y=cy+math.sin(angle)*i*17
            lobe(x,y,max(9,length),max(5,length*.38),angle,.9)
        cut(cx+flip*34,cy-flip*20,31,16,flip*.45,1.0)
    elif topology==1:  # pinched hourglass / two masses about to separate
        lobe(cx-flip*43,cy-r.range(-9,10),52,29,flip*.15,1.15)
        lobe(cx+flip*43,cy+r.range(-13,14),48,25,-flip*.25,1.15)
        lobe(cx,cy,29,9,0,.8); cut(cx,cy-r.range(15,27),35,18,0,.95); cut(cx,cy+r.range(15,27),35,18,0,.95)
    elif topology==2:  # buckled fold: an imperfect cavity, sometimes nearly open
        count=r.range(7,11); base=r.range(31,49); squash=.48+r.unit()*.25
        phase=r.unit()*math.tau; missing=r.range(0,count) if r.chance(.45) else -1
        for i in range(count):
            if i==missing: continue
            angle=phase+i*math.tau/count+(r.unit()-.5)*.24
            radius=base*(.76+r.unit()*.42)+math.sin(angle*2+phase)*r.range(3,11)
            thickness=.72+r.unit()*.55
            x=cx+math.cos(angle)*radius; y=cy+math.sin(angle)*radius*squash
            lobe(x,y,24*thickness,10+r.unit()*7,angle+math.pi/2,.82+r.unit()*.2)
        # Off-centre overlapping cuts buckle the interior instead of stamping a circle.
        cut(cx+r.range(-14,15),cy+r.range(-9,10),r.range(22,35),r.range(11,21),
            (r.unit()-.5)*.7,1.35)
        if r.chance(.55):
            cut(cx+flip*r.range(15,30),cy-flip*r.range(7,20),r.range(13,24),r.range(7,15),flip*.55,1.0)
        lobe(cx-flip*base*r.range(12,18)/10,cy+flip*r.range(15,34),r.range(26,45),r.range(8,16),flip*.35,.7)
    elif topology==3:  # broad animal-like cloud with hanging tendrils
        lobe(cx,cy-10,67,30,0,1.2); lobe(cx-flip*53,cy-3,43,22,flip*.2,1)
        for i in range(r.range(2,5)):
            x=cx+r.range(-62,63); length=r.range(25,61)
            lobe(x,cy+length*.35,12,30,flip*(.2+r.unit()*.35),.78)
            lobe(x+flip*r.range(8,19),cy+length*.75,8,20,flip*.45,.65)
        cut(cx+flip*35,cy-22,27,14,flip*.2,.8)
    else:  # collision: main body and one or two satellite flocks
        lobe(cx-flip*24,cy,60,34,flip*.12,1.2); lobe(cx+flip*28,cy-flip*9,40,19,-flip*.3,.9)
        cut(cx+flip*17,cy+flip*20,30,19,-flip*.3,.9)
        sx=cx+flip*r.range(82,108); sy=cy+flip*r.range(-32,33)
        lobe(sx,sy,r.range(16,27),r.range(8,15),flip*.3,.82)
        if r.chance(.5): lobe(cx-flip*r.range(78,111),cy-flip*r.range(25,44),r.range(10,20),r.range(6,12),-flip*.4,.7)

    def oval(x,y,item):
        cx0,cy0,rx,ry,angle,weight=item; ca,sa=math.cos(angle),math.sin(angle)
        dx=x-cx0; dy=y-cy0; u=dx*ca+dy*sa; v=-dx*sa+dy*ca
        return weight*math.exp(-(u*u/(2*rx*rx)+v*v/(2*ry*ry)))
    density=.62+r.unit()*.22; phase=r.unit()*math.tau
    if diffusion:
        resolution=2 if fine else 1
        output_w,output_content_h=W*resolution,CONTENT_H*resolution
        a=[[15 for _ in range(output_w)] for _ in range(H*resolution)]
        values=[]
        for y in range(output_content_h):
            row=[]
            for x in range(output_w):
                sample_x,sample_y=x/resolution,y/resolution
                field=sum(oval(sample_x,sample_y,item) for item in lobes)-sum(oval(sample_x,sample_y,item) for item in cuts)
                # Convert flock density into a smooth ink pressure. The gentle
                # edge becomes scattered pixels naturally during diffusion.
                # Reserve solid black for only the most compressed core; most
                # of the volume should remain visibly dithered.
                darkness=max(0,min(.90,(field-.055)*.62))
                row.append(lround((1-darkness)*4096))
            values.append(row)
        for y in range(output_content_h):
            for x in range(output_w):
                old=values[y][x]; quantized=4096 if old>=2048 else 0
                a[y][x]=15 if quantized else 0; error=int((old-quantized)/8)
                for sx,sy in ((x+1,y),(x+2,y),(x-1,y+1),(x,y+1),(x+1,y+1),(x,y+2)):
                    if 0<=sx<output_w and 0<=sy<output_content_h:
                        values[sy][sx]=max(-8192,min(12288,values[sy][sx]+error))
        return a
    for y in range(3,CONTENT_H-3,2):
        for x in range(3,W-3,2):
            positive=[oval(x,y,item) for item in lobes]; field=sum(positive)-sum(oval(x,y,item) for item in cuts)
            probability=max(0,min(.96,(field-.16)*density))
            if r.unit()>probability: continue
            strongest=max(range(len(positive)),key=positive.__getitem__); flow=lobes[strongest][4]
            flow+=.55*math.sin(x*.034+y*.051+phase)
            tone=0 if field>.82 else (r.range(0,4) if field>.48 else r.range(3,9))
            put(a,x,y,tone)
            # Predominantly isolated marks prevent neighboring strokes from
            # joining into maze-like horizontal corridors.
            if r.chance(.18):
                dx=1 if math.cos(flow)>=0 else -1
                dy=1 if math.sin(flow)>=0 else -1
                put(a,x+dx,y+dy,tone)
            if field>.9 and r.chance(.10): put(a,x,y+1,r.range(0,3))
    return a

def topography(seed):
    r=FirmwareRandom(seed); a=canvas(0); count=r.range(5,9)
    hills=[]
    for _ in range(count):
        x=r.range(-35,W+36); y=r.range(-28,CONTENT_H+29); rx=r.range(25,72); ry=r.range(18,55)
        height=r.unit()*1.6+.45 if r.chance(.62) else -(r.unit()*1.1+.35)
        hills.append((x,y,rx,ry,height))
    phase=r.unit()*math.tau; warp_phase=r.unit()*math.tau; interval=.31+r.unit()*.10
    elevation=[]
    for y in range(CONTENT_H):
        row=[]
        for x in range(W):
            wx=x+10*math.sin(y*.035+warp_phase)+4*math.sin((x+y)*.021-phase)
            wy=y+8*math.cos(x*.027-phase)+3*math.cos((x-y)*.019+warp_phase)
            value=.28*math.sin(wx*.030+phase)+.22*math.cos(wy*.043-phase*.7)+.15*math.sin((wx+wy)*.019)
            for hx,hy,rx,ry,height in hills:
                dx=wx-hx; dy=wy-hy
                value+=height*math.exp(-(dx*dx/(2*rx*rx)+dy*dy/(2*ry*ry)))
            row.append(value)
        elevation.append(row)
    ink=r.range(11,16)
    for y in range(CONTENT_H-1):
        for x in range(W-1):
            band=math.floor(elevation[y][x]/interval)
            if band!=math.floor(elevation[y][x+1]/interval) or band!=math.floor(elevation[y+1][x]/interval):
                block(a,x,y,2,2,ink)
    return a

def amoeba(seed):
    r=FirmwareRandom(seed); a=canvas(15); cell=2 if r.chance(.72) else 3
    cols=W//cell; rows=CONTENT_H//cell; ecology=r.range(0,4); focus_count=r.range(2,6)
    focuses=[(r.range(0,cols),r.range(0,rows),r.range(7,22),1 if r.chance(.72 if ecology==2 else .5) else -1) for _ in range(focus_count)]
    phase=r.unit()*math.tau
    base=(.34+r.unit()*.06) if ecology==0 else ((.50+r.unit()*.08) if ecology==2 else (.40+r.unit()*.09))
    current=[]
    for y in range(rows):
        row=[]
        for x in range(cols):
            field=sum(weight*math.exp(-((x-fx)**2+(y-fy)**2)/(2*radius*radius)) for fx,fy,radius,weight in focuses)
            drift=.06*math.sin(x*.10+phase)+.05*math.cos(y*.14-phase*.6)
            if ecology==1: drift+=.13*math.sin((x+y)*.075+phase)
            elif ecology==3: drift+=.11*math.cos((x-y)*.09-phase)
            drift+=field*(.16 if ecology==0 else .11)
            row.append(r.unit()<max(.24,min(.68,base+drift)))
        current.append(row)
    generations=r.range(3,6) if ecology==0 else (r.range(6,10) if ecology==2 else r.range(4,9))
    for _ in range(generations):
        nxt=[[False for _ in range(cols)] for _ in range(rows)]
        for y in range(rows):
            for x in range(cols):
                neighbors=sum(current[(y+dy)%rows][(x+dx)%cols] for dy in (-1,0,1) for dx in (-1,0,1) if dx or dy)
                survive=5 if ecology==2 else 4; birth=4 if ecology==3 else 5
                nxt[y][x]=neighbors>=survive if current[y][x] else neighbors>=birth
        current=nxt
    field=[[4080 if current[y//cell][x//cell] else 0 for x in range(W)] for y in range(CONTENT_H)]
    for _ in range(r.range(6,12)):
        softened=[]
        for y in range(CONTENT_H):
            row=[]
            for x in range(W):
                values=[field[sy][sx] for sy in range(max(0,y-1),min(CONTENT_H,y+2)) for sx in range(max(0,x-1),min(W,x+2))]
                row.append((sum(values)//len(values)//16)*16)
            softened.append(row)
        field=softened
    nested=r.chance(.34); interval=r.range(1350,1900) if nested else r.range(1900,2800); ink=r.range(0,5)
    for y in range(CONTENT_H-1):
        for x in range(W-1):
            band=field[y][x]//interval
            if band!=field[y][x+1]//interval or band!=field[y+1][x]//interval: put(a,x,y,ink)
    return a

SYSTEMS={
    "scanline-erosion":scanline_erosion,
    "motif-field":motif_field,
    "dither-architecture":dither_architecture,
    "cellular-aggregate":cellular_aggregate,
    "dual-cellular-overlap":lambda seed: dual_cellular(seed,"overlap"),
    "dual-cellular-boundary":lambda seed: dual_cellular(seed,"boundary"),
    "dual-cellular-attractor":dual_cellular_attractor,
    "pixel-field":pixel_field,
    "subdivision":lambda seed: subdivision(seed),
    "subdivision-woven-checks":lambda seed: subdivision(seed,0),
    "subdivision-open-windows":lambda seed: subdivision(seed,1),
    "subdivision-diagonals":lambda seed: subdivision(seed,2),
    "subdivision-corner-knots":lambda seed: subdivision(seed,3),
    "dither-pressure-ordered":lambda seed: dither_pressure(seed,0),
    "dither-pressure-diffusion":lambda seed: dither_pressure(seed,1),
    "dither-pressure":lambda seed: dither_pressure(seed),
    "murmuration":murmuration,
    "murmuration-diffusion":lambda seed: murmuration(seed,True),
    "murmuration-diffusion-half-pixels":lambda seed: murmuration(seed,True,True),
    "topography":topography,
    "amoeba":amoeba,
    "dither-pressure-ordered-large":lambda seed: dither_pressure(seed,0,4),
    "dither-pressure-diffusion-large":lambda seed: dither_pressure(seed,1,4),
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("systems",nargs="*",choices=SYSTEMS.keys())
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    selected=args.systems or SYSTEMS.keys()
    for name in selected:
        generator=SYSTEMS[name]
        folder=OUT/name; folder.mkdir(exist_ok=True)
        images=[]
        for i in range(50):
            image=generator(0xDA17_0000+i); images.append(image)
            path=folder/f"{i:02d}.pgm"; write_pgm(image,path)
        sheet=OUT/f"{name}.png"
        raw=OUT/f"{name}-sheet.pgm"; write_sheet(images,raw)
        subprocess.run(["magick",str(raw),str(sheet)],check=True)
        print(sheet)

if __name__=="__main__": main()
