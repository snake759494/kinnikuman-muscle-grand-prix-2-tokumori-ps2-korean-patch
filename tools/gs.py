import struct,numpy as np
def hdr(d): return struct.unpack_from('<8I',d,0x10)
def load(pix,pal):
    h=hdr(pix); psm=h[1]; w,hh=h[2],h[3]
    body=pix[0x80:]
    if psm==0x14:
        a=np.frombuffer(body,np.uint8)[:w*hh//2]; idx=np.empty(a.size*2,np.uint8); idx[0::2]=a&15; idx[1::2]=a>>4
    elif psm==0x13:
        idx=np.frombuffer(body,np.uint8)[:w*hh].copy()
    else: raise ValueError(hex(psm))
    ph=hdr(pal); cols=np.frombuffer(pal[0x80:],np.uint8).reshape(-1,4).copy()
    if psm==0x13 and len(cols)==256:  # CSM1 unswizzle
        c=cols.reshape(8,2,2,8,4).transpose(0,2,1,3,4).reshape(256,4); cols=c
    return idx.reshape(hh,w),cols,psm
def rgba(idx,cols):
    c=cols[idx].astype(np.int32); c[...,3]=np.minimum(c[...,3]*2,255); return c.astype(np.uint8)
