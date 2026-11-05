"""AFS→PACK(중첩)→파일 재귀 순회."""
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
import afs
from pack import PACK
def walk(cb, skip_char=True):
    f=open(afs.ISO,'rb');n,ent=afs.table(f);nm=afs.names()
    def rec(path,d):
        cb(path,d)
        if d[:4]==b'PACK':
            p=PACK(d)
            for a,x in zip(p.names,p.data): rec(path+'/'+a,x)
    for i in range(n):
        top=nm[i].split(chr(92))[0]
        if top in ('voice','bgm','movie','se','effect','stage'): continue
        if skip_char and nm[i].startswith('pack'+chr(92)+'char'): continue
        if ent[i][1]>20_000_000: continue
        rec(f'{i}:'+nm[i].replace(chr(92),'/'),afs.read(f,ent,i))
