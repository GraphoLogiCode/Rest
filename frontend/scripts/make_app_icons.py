"""Rasterize Rest's existing code-drawn R/leaf mark for home-screen icons."""
from pathlib import Path
from PIL import Image, ImageDraw
OUT=Path(__file__).resolve().parents[1]/'public/icons'
OUT.mkdir(exist_ok=True)

def cubic(start, one, two, end):
    return [tuple((1-t)**3*start[j]+3*(1-t)**2*t*one[j]+3*(1-t)*t*t*two[j]+t**3*end[j] for j in (0,1)) for t in [i/64 for i in range(65)]]

def icon(size, safe=False):
    scale=4*size/64
    image=Image.new('RGB',(size*4,size*4),'#F8F7F4');draw=ImageDraw.Draw(image)
    transform=lambda p:tuple(round((32+(v-32)*(.8 if safe else 1))*scale) for v in p)
    line=[(20,47),(20,17),(32,17),*cubic((32,17),(47,17),(48,36),(32,36)),(20,36)]
    draw.line([transform(p) for p in line],fill='#3f5546',width=round(5*scale*(.8 if safe else 1)),joint='curve')
    draw.line([transform((32,36)),transform((46,47))],fill='#3f5546',width=round(5*scale*(.8 if safe else 1)))
    leaf=cubic((47,11),(38,11),(35,16),(36,22))+cubic((36,22),(44,22),(48,19),(47,11))
    draw.polygon([transform(p) for p in leaf],fill='#be9856')
    return image.resize((size,size),Image.Resampling.LANCZOS)

for name,size,safe in [('rest-192.png',192,False),('rest-512.png',512,False),('rest-maskable-512.png',512,True),('apple-touch-icon.png',180,False)]:
    icon(size,safe).save(OUT/name)
print('Generated four Rest home-screen icons from the established mark.')
