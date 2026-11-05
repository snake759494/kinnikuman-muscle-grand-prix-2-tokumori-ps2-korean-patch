import struct
class PACK:
    def __init__(s,d):
        s.hdr=bytearray(d[:0x10]); n,s.align=struct.unpack_from('<II',d,0x10)
        s.delta=len(d)-struct.unpack_from('<I',d,4)[0]
        ents=[struct.unpack_from('<3I',d,0x18+12*i) for i in range(n)]
        s.names=[d[a:d.index(b'\0',a)].decode('cp932') for a,_,_ in ents]
        s.data=[d[o:o+z] for _,o,z in ents]
        s.nameblob_off=ents[0][0]; s.first=ents[0][1]
        s.pre=d[0x18+12*n:s.first]   # 이름 테이블 포함 영역 그대로
        s.ents=ents; s.orig_len=len(d)
    def build(s):
        out=bytearray(s.hdr)+struct.pack('<II',len(s.data),s.align)
        tab=bytearray(); body=bytearray(); pos=s.first
        offs=[]
        for x in s.data:
            offs.append(pos); body+=x; pad=(-len(x))%s.align; body+=b'\0'*pad; pos+=len(x)+pad
        for (a,_,_),o,x in zip(s.ents,offs,s.data): tab+=struct.pack('<3I',a,o,len(x))
        out+=tab+s.pre+body
        struct.pack_into('<I',out,4,len(out)-s.delta)
        return bytes(out)
    def get(s,name): return s.data[s.names.index(name)]
    def set(s,name,b): s.data[s.names.index(name)]=b
