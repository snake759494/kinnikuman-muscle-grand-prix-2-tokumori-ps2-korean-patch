"""CXML: 'CXML' u32 size(=len-delta) u32 ver u32 0, 24바이트 노드[name,value,parent,child,next,?], 문자열 풀."""
import struct


class CXML:
    def __init__(s, d):
        s.hdr = bytearray(d[:0x10])
        first = min(v for v in struct.unpack_from('<6i', d, 0x10)[:2] if v >= 0)
        n = (first - 0x10) // 24
        s.nodes = [list(struct.unpack_from('<6i', d, 0x10 + 24 * i)) for i in range(n)]
        s.tail = d[0x10 + 24 * n:first]

        def gs(o):
            return d[o:d.index(b'\0', o)]
        s.name = [gs(r[0]) if r[0] >= 0 else None for r in s.nodes]
        s.val = [gs(r[1]) if r[1] >= 0 else None for r in s.nodes]
        end = max(d.index(b'\0', x) + 1 for r in s.nodes for x in r[:2] if x >= 0)
        s.pad = d[end:]
        s.delta = len(d) - struct.unpack_from('<I', d, 4)[0]

    def build(s):
        pool = bytearray()
        base = 0x10 + 24 * len(s.nodes) + len(s.tail)

        def put(b):
            if b is None:
                return -1
            o = base + len(pool)
            pool.extend(b + b'\0')
            return o
        out = bytearray(s.hdr)
        recs = bytearray()
        for r, nm, v in zip(s.nodes, s.name, s.val):
            r = r[:]
            r[0] = put(nm)
            r[1] = put(v)
            recs += struct.pack('<6i', *r)
        out += recs + s.tail + pool + s.pad
        struct.pack_into('<I', out, 4, len(out) - s.delta)
        return bytes(out)

    def path(s, i):
        p = []
        while i >= 0:
            p.append(s.name[i].decode('cp932'))
            i = s.nodes[i][2]
        return '/'.join(reversed(p))
