"""원본 ISO를 복사해 파일을 교체한다.

- 새 파일이 원래 자리(다음 파일 시작 섹터까지)에 들어가면 제자리 기록 + 디렉터리 레코드의 크기만 수정.
- 넘치면 ISO 끝(마지막 섹터 뒤)에 붙이고 디렉터리 레코드의 위치·크기를 고친 뒤 PVD의 볼륨 크기를 늘린다.
"""
import os, struct, shutil

SEC = 2048


def _dir_records(f, lba, size):
    f.seek(lba * SEC)
    data = f.read(size)
    out, p = [], 0
    while p < len(data):
        ln = data[p]
        if ln == 0:
            p = (p // SEC + 1) * SEC
            continue
        flags = data[p + 25]
        nl = data[p + 32]
        name = data[p + 33:p + 33 + nl]
        out.append((lba * SEC + p, name, struct.unpack_from('<I', data, p + 2)[0],
                    struct.unpack_from('<I', data, p + 10)[0], flags))
        p += ln
    return out


def walk(f):
    """{'/DIR/FILE.EXT': (레코드 위치, lba, size)}"""
    f.seek(16 * SEC + 156)
    root = f.read(34)
    res, stack = {}, [('', struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0])]
    while stack:
        path, lba, size = stack.pop()
        for pos, name, l, s, flags in _dir_records(f, lba, size):
            if name in (b'\0', b'\1'):
                continue
            n = name.decode('ascii').split(';')[0]
            if flags & 2:
                stack.append((path + '/' + n, l, s))
            else:
                res[path + '/' + n] = (pos, l, s)
    return res


def patch(src_iso, dst_iso, files):
    """files: {'/LANGUAGE/STRINGS/MAINJA.BIN': bytes}"""
    shutil.copyfile(src_iso, dst_iso)
    with open(src_iso, 'rb') as s:
        table = walk(s)
    starts = sorted(l for _, l, _ in table.values())
    log = []
    with open(dst_iso, 'r+b') as f:
        f.seek(16 * SEC + 80)
        vol = struct.unpack('<I', f.read(4))[0]
        end = os.path.getsize(src_iso) // SEC
        for path, data in files.items():
            pos, lba, size = table[path]
            nxt = min([x for x in starts if x > lba] + [end])
            room = (nxt - lba) * SEC
            if len(data) <= room:
                where = lba
            else:
                where = end
                end += (len(data) + SEC - 1) // SEC
            f.seek(where * SEC)
            f.write(data + bytes(-len(data) % SEC))
            if where == lba and len(data) < size:  # 남는 꼬리는 0으로
                f.write(bytes(((size + SEC - 1) // SEC) * SEC - ((len(data) + SEC - 1) // SEC) * SEC))
            f.seek(pos + 2); f.write(struct.pack('<I', where) + struct.pack('>I', where))
            f.seek(pos + 10); f.write(struct.pack('<I', len(data)) + struct.pack('>I', len(data)))
            log.append((path, lba, where, size, len(data)))
        if end > vol:
            f.seek(16 * SEC + 80); f.write(struct.pack('<I', end) + struct.pack('>I', end))
            f.truncate(end * SEC)
    return log
