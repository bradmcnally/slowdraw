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
def write_pgm(a,path):
    with path.open("wb") as f:
        f.write(f"P5\n{W} {H}\n255\n".encode())
        f.write(bytes(v*17 for row in a for v in row))

def write_sheet(images,path):
    scale,gap,cols,rows=2,8,5,10
    sw=cols*W*scale+(cols+1)*gap; sh=rows*H*scale+(rows+1)*gap
    sheet=[[216 for _ in range(sw)] for _ in range(sh)]
    for i,a in enumerate(images):
        ox=gap+(i%cols)*(W*scale+gap); oy=gap+(i//cols)*(H*scale+gap)
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
