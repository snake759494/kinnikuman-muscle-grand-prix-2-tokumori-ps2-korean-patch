"""PFNT 재구성: 원본의 가나·기호·ASCII(<0x889F)는 유지, 한자 칸을 버리고 한글을 0x889F~ 코드에 배치."""
import struct, os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from pft import PFT
ROOT = os.path.join(os.path.dirname(__file__), '..')

def sjis_codes(start=0x889F):
    c = start
    while True:
        lead, tr = c >> 8, c & 0xff
        if 0x40 <= tr <= 0xfc and tr != 0x7f and (0x81 <= lead <= 0x9f or 0xe0 <= lead <= 0xfc):
            yield c
        c += 1
        if (c & 0xff) > 0xfc:
            c = ((c >> 8) + 1) << 8 | 0x40
            if (c >> 8) == 0xa0: c = 0xe040

def charmap(chars, skip=()):
    g = sjis_codes(); out = {}
    for ch in chars:
        c = next(g)
        while c in skip: c = next(g)
        out[ch] = c
    return out

def enc(c, a):
    """4비트 색(c)·4비트 알파(a)를 원본 팔레트(스위즐된 CLUT) 인덱스로."""
    return (c & 7) | ((c >> 3) & 1) << 4 | (a & 1) << 3 | (a >> 1) << 5

def render(ch, font, size_box=32, base=26, dx=0, bold=0.3):
    """원본 글자처럼: 알파=테두리까지 포함한 덮임, 색=테두리 8·안쪽 15."""
    from PIL import ImageFilter
    S = 4
    im = Image.new('L', (64 * S, 64 * S)); dr = ImageDraw.Draw(im)
    font = ImageFont.truetype(font.path, font.size * S)
    dr.text((8 * S, (8 + base) * S), ch, font=font, fill=255, anchor='ls',
            stroke_width=int(bold * S), stroke_fill=255)
    out = im.filter(ImageFilter.MaxFilter(S + 1))      # 약 0.6px 테두리
    f = np.array(im.resize((64, 64), Image.BOX)).astype(float) / 255
    o = np.array(out.resize((64, 64), Image.BOX)).astype(float) / 255
    cols = np.where(o.max(0) > 0.05)[0]
    if len(cols) == 0: return np.zeros((32, 32), np.uint8), 0
    x0, x1 = cols.min(), cols.max()
    w = min(32, x1 - x0 + 1)
    F = f[8:40, x0:x0 + w]; O = o[8:40, x0:x0 + w]
    A = np.rint(O * 15).astype(int)
    C = np.rint(8 + 7 * np.clip(F / np.maximum(O, 1e-6), 0, 1)).astype(int)
    C[A == 0] = 0
    g = np.zeros((32, 32), np.uint8)
    g[:, :w] = np.vectorize(enc)(C, A)
    return g, w

def build(src, korean, ttf, px, base, adv=25, out=None, keep=(), keep_glyphs=True, low=None):
    p = PFT(src); codes = p.codes()
    keepk = set(keep)
    keep = {c: i for c, i in codes.items()
            if (c < 0x889F and (low is None or c < 0x100 or c in low)) or (keep_glyphs and c in keepk)}
    glyphs = []; widths = []; table = {}
    for c in sorted(keep):
        table[c] = len(glyphs); glyphs.append(p.glyph(keep[c]).copy()); widths.append(p.width(keep[c]))
    font = ImageFont.truetype(ttf, px)
    cm = charmap(korean, skip=keepk)
    for ch, c in cm.items():
        g, w = render(ch, font, base=base)
        left = max(0, (adv - w) // 2)
        table[c] = len(glyphs); glyphs.append(g); widths.append((left, adv - left))
    # 표
    leads = sorted({c >> 8 for c in table if c >= 0x100})
    top = [-1] * 256
    for c in table:
        if c < 0x100: top[c] = table[c]
    tab = bytearray()
    sub_base = 0x44 + 1024
    subs = bytearray()
    for k, lead in enumerate(leads):
        top[lead] = sub_base + 1024 * k
        s = [-1] * 256
        for c in table:
            if c >> 8 == lead: s[c & 0xff] = table[c]
        subs += struct.pack('<256i', *s)
    tab = struct.pack('<256i', *top) + subs
    hdr = bytearray(p.d[:0x44])
    wtab = 0x44 + len(tab)
    wt = b''.join(struct.pack('<hh', *w) for w in widths)
    pal = (wtab + len(wt) + 0xff) // 0x100 * 0x100
    pal = max(pal, wtab + len(wt))
    # 원본처럼 0x200 정렬
    pal = (wtab + len(wt) + 0x3f) // 0x40 * 0x40
    gdat = pal + 0x400
    out = bytearray(hdr + tab + wt)
    out += b'\0' * (pal - len(out))
    out += p.d[p.pal:p.pal + 0x400]
    for g in glyphs: out += g.tobytes()
    struct.pack_into('<I', out, 0x28, wtab); struct.pack_into('<I', out, 0x2c, pal); struct.pack_into('<I', out, 0x30, gdat)
    struct.pack_into('<I', out, 4, len(out) - 8)
    return bytes(out), cm
