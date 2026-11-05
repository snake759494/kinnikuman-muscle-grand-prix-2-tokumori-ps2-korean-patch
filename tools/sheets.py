import json,sys,os,re
from PIL import Image,ImageDraw
idx=json.load(open('work/tex/index.json',encoding='utf8'))
def cat(e):
    p=e['paths'][0].split(':',1)[1]
    return re.sub(r'\d+','#',p.rsplit('/',1)[0])
sel=[e for e in idx if (sys.argv[1] in cat(e))] if len(sys.argv)>1 else idx
excl=sys.argv[2] if len(sys.argv)>2 else None
if excl: sel=[e for e in sel if excl not in cat(e)]
os.makedirs('work/sheets',exist_ok=True)
TW=200;COLS=6;page=0;y=0;x=0;rowh=0
sheet=Image.new('RGB',(TW*COLS,1400),(70,70,110));dr=ImageDraw.Draw(sheet)
def flush():
    global sheet,dr,page
    sheet.save(f'work/sheets/{(sys.argv[1] if len(sys.argv)>1 else "all").replace("/","_")}_{page:02d}.png');page+=1
    sheet=Image.new('RGB',(TW*COLS,1400),(70,70,110));dr=ImageDraw.Draw(sheet)
for e in sel:
    im=Image.open(f"work/tex/{e['name']}.png")
    s=min(1,TW/im.width,300/im.height); t=im.resize((max(1,int(im.width*s)),max(1,int(im.height*s))))
    if x+1>COLS: x=0;y+=rowh+14;rowh=0
    if y+t.height+14>1400: flush();x=0;y=0;rowh=0
    sheet.paste(t,(x*TW,y+12),t); dr.text((x*TW+2,y),e['name']+' '+e['paths'][0].split('/')[-1][:22],fill=(255,255,0))
    rowh=max(rowh,t.height);x+=1
flush()
