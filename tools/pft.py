import struct,numpy as np
class PFT:
    def __init__(s,d):
        s.d=bytearray(d); h=struct.unpack_from('<16I',d,4)
        s.wtab,s.pal,s.gdat=h[9],h[10],h[11]
        s.n=(len(d)-s.gdat)//1024
    def idx(s,code):
        t=lambda o:struct.unpack_from('<i',s.d,o)[0]
        if code<0x100: return t(0x44+4*code)
        o=t(0x44+4*(code>>8))
        if o<0: return -1
        return t(o+4*(code&0xff))
    def codes(s):
        r={}
        for c in range(0x100):
            v=s.idx(c)
            if v>=0 and c not in range(0x81,0xa0) and c not in range(0xe0,0x100): r[c]=v
        for lead in list(range(0x81,0xa0))+list(range(0xe0,0x100)):
            o=struct.unpack_from('<i',s.d,0x44+4*lead)[0]
            if o<0 or o>=s.wtab: continue
            for tr in range(256):
                v=struct.unpack_from('<i',s.d,o+4*tr)[0]
                if v>=0: r[(lead<<8)|tr]=v
        return r
    def glyph(s,i): return np.frombuffer(bytes(s.d[s.gdat+1024*i:s.gdat+1024*i+1024]),np.uint8).reshape(32,32)
    def width(s,i): return struct.unpack_from('<hh',s.d,s.wtab+4*i)
