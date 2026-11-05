import struct
ISO='Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan).iso'
BASE=278*2048
def table(f):
    f.seek(BASE); h=f.read(8); n=struct.unpack('<I',h[4:])[0]
    t=f.read(8*(n+1)); ent=[struct.unpack_from('<II',t,8*i) for i in range(n+1)]
    return n,ent
def read(f,ent,i):
    o,s=ent[i]; f.seek(BASE+o); return f.read(s)
def names():
    import os
    here=os.path.dirname(os.path.abspath(__file__))
    r=[]
    for l in open(os.path.join(here,'..','extract','filelist.tsv'),encoding='utf8'):
        a=l.rstrip('\n').split('\t'); r.append(a[3])
    return r
def dump(pred,out='extract/afs'):
    import os
    f=open(ISO,'rb');n,ent=table(f);nm=names()
    for i in range(n):
        if pred(i,nm[i]):
            p=os.path.join(out,nm[i].replace(chr(92),'/')); os.makedirs(os.path.dirname(p),exist_ok=True)
            open(p,'wb').write(read(f,ent,i))
