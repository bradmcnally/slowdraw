#!/usr/bin/env python3
"""Generate Slow Draw contact sheets with only the Python standard library."""

from pathlib import Path
import argparse, math, random, subprocess

W, H = 240, 124
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "studies"

def canvas(value=15): return [[value for _ in range(W)] for _ in range(H)]
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

def cellular_aggregate(seed):
    r=random.Random(seed); a=canvas(r.choice([14,15])); unit=r.choice([5,6,8,10]); x=r.randrange(7,W//unit-7); y=r.randrange(5,H//unit-5)
    cells={(x,y)}
    for _ in range(r.randint(45,100)):
        bx,by=r.choice(tuple(cells)); dx,dy=r.choice(((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1)))
        nx,ny=bx+dx,by+dy
        if 1<=nx<W//unit-1 and 1<=ny<H//unit-1: cells.add((nx,ny))
    # Value comes from position within the aggregate, not independent randomness.
    cx=sum(x for x,y in cells)/len(cells); cy=sum(y for x,y in cells)/len(cells)
    for x,y in cells:
        angle=math.atan2(y-cy,x-cx); radius=math.hypot(x-cx,y-cy)
        value=max(0,min(14,round(7+5*math.sin(angle*2.3+radius*.7))))
        gap=r.choice([0,0,1]); block(a,x*unit+gap,y*unit+gap,unit-gap,unit-gap,value)
    # A few detached echoes preserve negative space.
    for _ in range(r.randint(3,9)):
        x,y=r.choice(tuple(cells)); x+=r.choice((-3,3)); y+=r.choice((-3,3))
        block(a,x*unit,y*unit,unit,unit,r.randrange(3,13))
    return a

def subdivision(seed, language):
    r=random.Random(seed); a=canvas(15); macro=r.choice([8,10,10,10,10,12]); sub=2
    cols,rows,cells=W//macro,120//macro,macro//sub
    centers=[(r.randrange(cols),r.randrange(rows),r.uniform(3,8),r.choice([-1,1])) for _ in range(r.randint(3,5))]
    phase=r.randrange(6); dark=r.randrange(0,5); mid=r.randrange(7,13)
    for gy in range(rows):
        for gx in range(cols):
            field=sum(sign*math.exp(-((gx-cx)**2+(gy-cy)**2)/(2*s*s)) for cx,cy,s,sign in centers)
            rhythm=.12*math.sin(gx*.73+gy*.41+phase)
            presence=max(.10,min(.86,.43+field*.24+rhythm))
            if r.random()>presence: continue
            dense=field>.55 and r.random()<.28
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

SYSTEMS={
    "scanline-erosion":scanline_erosion,
    "motif-field":motif_field,
    "dither-architecture":dither_architecture,
    "cellular-aggregate":cellular_aggregate,
    "subdivision-woven-checks":lambda seed: subdivision(seed,0),
    "subdivision-open-windows":lambda seed: subdivision(seed,1),
    "subdivision-diagonals":lambda seed: subdivision(seed,2),
    "subdivision-corner-knots":lambda seed: subdivision(seed,3),
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
