"""EFPK(이펙트) 안 GSL 텍스처 목록·디코드·교체."""
import struct, numpy as np
def gsl_off(d): return d.index(b'GSL ')
def textures(d):
    o = gsl_off(d); g = d[o:]
    cnt = struct.unpack_from('<I', g, 0x14)[0]
    words = struct.unpack_from('<%dI' % ((0x20 + cnt * 0x60) // 4), g, 0)
    out = []
    for i in range(8, len(words) - 17):
        p = words[i]
        if p in (0x13, 0x14) and words[i + 4] == p and words[i + 7] == 0x40 and words[i + 11] in (0x10, 0x8):
            w, h = words[i + 1], words[i + 2]
            if w and h and 1 << words[i + 5] >= w and 1 << words[i + 6] >= h:
                out.append(dict(psm=p, w=w, h=h, pix=o + words[i - 6], pal=o + words[i - 5], hdr=o + 4 * i))
    return out
def unswz(c): return c.reshape(8, 2, 2, 8, 4).transpose(0, 2, 1, 3, 4).reshape(256, 4)
def swz(c): return c.reshape(8, 2, 2, 8, 4).transpose(0, 2, 1, 3, 4).reshape(256, 4)
def decode(d, t):
    w, h = t['w'], t['h']
    if t['psm'] == 0x13:
        idx = np.frombuffer(d[t['pix']:t['pix'] + w * h], np.uint8).reshape(h, w)
        c = unswz(np.frombuffer(d[t['pal']:t['pal'] + 1024], np.uint8).reshape(256, 4))
    else:
        a = np.frombuffer(d[t['pix']:t['pix'] + w * h // 2], np.uint8)
        idx = np.empty(a.size * 2, np.uint8); idx[0::2] = a & 15; idx[1::2] = a >> 4; idx = idx.reshape(h, w)
        c = np.frombuffer(d[t['pal']:t['pal'] + 64], np.uint8).reshape(16, 4)
    return idx, c.copy()
def rgba(idx, c):
    x = c[idx].astype(int); x[..., 3] = np.minimum(x[..., 3] * 2, 255); return x.astype(np.uint8)
