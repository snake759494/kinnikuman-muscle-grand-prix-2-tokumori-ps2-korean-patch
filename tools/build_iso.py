"""원본 ISO + 교체할 AFS 항목/ISO 파일 → 새 ISO.
DATA.BIN(LBA 278)을 다시 쓰고 그 뒤 파일들은 새 위치로 옮긴다."""
import struct, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import afs, isopatch
SEC = 2048

def up(x, a): return (x + a - 1) // a * a

def build(dst, afs_rep, iso_rep=None):
    iso_rep = iso_rep or {}
    src = open(afs.ISO, 'rb'); n, ent = afs.table(src)
    files = isopatch.walk(src)
    # FLST 갱신
    flst = bytearray(afs_rep.get(0) or afs.read(src, ent, 0))
    sizes = []
    for i in range(n):
        sizes.append(len(afs_rep[i]) if i in afs_rep else ent[i][1])
    for i in range(n):
        o = struct.unpack_from('<I', flst, 8 + 4 * i)[0]
        struct.pack_into('<I', flst, o, up(sizes[i], 0x800))
    afs_rep = dict(afs_rep); afs_rep[0] = bytes(flst); sizes[0] = len(flst)
    out = open(dst + '.tmp', 'wb')
    src.seek(0); out.write(src.read(278 * SEC))
    base = 278 * SEC
    # 표
    first = ent[0][0]
    hdr = bytearray(first)
    src.seek(base); hdr[:] = src.read(first)
    pos = first; newent = []
    out.seek(base + first)
    for i in range(n):
        if i in afs_rep: d = afs_rep[i]
        else:
            src.seek(base + ent[i][0]); d = src.read(ent[i][1])
        newent.append((pos, len(d)))
        out.write(d); pad = up(len(d), 0x800) - len(d); out.write(b'\0' * pad); pos += len(d) + pad
    # 이름표
    src.seek(base + ent[n][0]); nt = src.read(ent[n][1])
    newent.append((pos, len(nt))); out.write(nt); pos += len(nt)
    pad = up(pos, SEC) - pos; out.write(b'\0' * pad); pos += pad
    for i, (o, s) in enumerate(newent): struct.pack_into('<II', hdr, 8 + 8 * i, o, s)
    out.seek(base); out.write(hdr)
    data_size = pos
    lba = 278 + data_size // SEC
    out.seek(lba * SEC)
    recs = {'/DATA.BIN': (278, data_size)}
    others = sorted([(v[1], k) for k, v in files.items() if k != '/DATA.BIN'])
    for _, k in others:
        rec, l, s = files[k]
        if k in iso_rep: d = iso_rep[k]
        else: src.seek(l * SEC); d = src.read(s)
        out.seek(lba * SEC); out.write(d); out.write(b'\0' * (up(len(d), SEC) - len(d)))
        recs[k] = (lba, len(d)); lba += up(len(d), SEC) // SEC
    # 원본 뒤쪽 여백 유지
    orig_total = os.path.getsize(afs.ISO) // SEC
    last_orig = max(l + up(s, SEC) // SEC for _, l, s in files.values())
    total = lba + (orig_total - last_orig)
    out.seek(total * SEC - 1); out.write(b'\0')
    for k, (l, s) in recs.items():
        rec = files[k][0]
        out.seek(rec + 2); out.write(struct.pack('<I', l) + struct.pack('>I', l))
        out.seek(rec + 10); out.write(struct.pack('<I', s) + struct.pack('>I', s))
    out.seek(16 * SEC + 80); out.write(struct.pack('<I', total) + struct.pack('>I', total))
    out.close(); src.close()
    os.replace(dst + '.tmp', dst)
