"""한글패치 빌드: 번역(translation/ko) + 폰트 + 이미지 → 근육맨 머슬그랑프리2 특상 한글판 ISO."""
import sys, os, re, struct, glob, json, collections, hashlib, time
sys.path.insert(0, os.path.dirname(__file__))
import afs, build_iso, build_font, units, tree
from cxml import CXML
from pack import PACK
from pft import PFT

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TR = os.path.join(ROOT, 'translation')
OUT_ISO = os.path.join(ROOT, 'Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan) [KO].iso')
ADV = 25   # 한글 진행폭
log = collections.Counter(); missing = collections.Counter(); warn = []


# ---------------------------------------------------------------- 번역 읽기
def read_tsv(p):
    rows = []
    for l in open(p, encoding='utf-8').read().splitlines()[1:]:
        a = l.split('\t')
        if len(a) >= 3: rows.append(a)
    return rows

def load_tr():
    single, lines, para, elf = {}, {}, {}, {}
    for n in ['s1', 's2', 's3']:
        for i, jp, ko in [r[:3] for r in read_tsv(os.path.join(TR, 'ko', n + '.tsv'))]:
            single[jp] = ko
    for i, jp, ko in [r[:3] for r in read_tsv(os.path.join(TR, 'ko', 's4.tsv'))]:
        if i.startswith('L_'): lines[jp] = ko
        else: elf[int(i[2:], 16)] = (jp, ko)
    for n in ['p1', 'p2', 'p3', 'p4']:
        p = os.path.join(TR, 'ko', n + '.tsv')
        if os.path.exists(p):
            for i, jp, ko in [r[:3] for r in read_tsv(p)]: para[jp] = ko
    fix = os.path.join(TR, 'fix.tsv')   # 검수 수정(원문\t번역) — 마지막에 덮어씀
    if os.path.exists(fix):
        for l in open(fix, encoding='utf-8').read().splitlines():
            if not l or l.startswith('#'): continue
            a = l.split('\t')
            for d in (single, lines, para):
                if a[0] in d: d[a[0]] = a[1]
            single.setdefault(a[0], a[1])
    return single, lines, para, elf


# ---------------------------------------------------------------- 문자 인코딩
SUB = {'·': '・', '　': ' '}
class Enc:
    def __init__(s, cm, widths):
        s.cm = cm; s.w = widths
    def __call__(s, t):
        out = bytearray()
        for ch in t:
            ch = SUB.get(ch, ch)
            if ch in s.cm:
                c = s.cm[ch]; out += bytes([c >> 8, c & 0xff])
            else:
                try: b = ch.encode('cp932')
                except UnicodeEncodeError:
                    warn.append('인코딩 불가 %r in %s' % (ch, t)); b = b'?'
                out += b
        return bytes(out)
    def width(s, t):
        b = s(t); i = 0; w = 0
        while i < len(b):
            if b[i] >= 0x81 and (b[i] < 0xa0 or b[i] >= 0xe0): c = (b[i] << 8) | b[i + 1]; i += 2
            else: c = b[i]; i += 1
            w += s.w.get(c, ADV)
        return w


def wrap(enc, text, nlines, maxw):
    """단어 단위 줄바꿈. 실패하면 글자 단위."""
    def go(tokens, joiner):
        ls = ['']
        for t in tokens:
            cand = (ls[-1] + joiner + t) if ls[-1] else t
            if enc.width(cand) <= maxw: ls[-1] = cand
            else:
                if enc.width(t) > maxw: return None
                ls.append(t)
        return ls
    r = go(text.split(' '), ' ')
    if r is None or len(r) > nlines:
        r = go(list(text), '')
        if r is not None:   # 글자 단위: 줄머리 공백 제거
            r = [x.strip() for x in r]
    if r is None or len(r) > nlines:
        warn.append('문단 넘침(%d줄): %s' % (len(r) if r else -1, text[:40]))
        r = (r or [text])[:nlines]
    return r + [''] * (nlines - len(r))


# ---------------------------------------------------------------- CXML / XML / 에피소드
class TextPatcher:
    def __init__(s, single, lines, para, enc):
        s.single, s.lines, s.para, s.enc = single, lines, para, enc

    def tr_single(s, t):
        if t in s.single:
            k = s.single[t]
            if k == '=': return None
            return k
        missing[t] += 1
        return None

    def cxm(s, d, fname):
        c = CXML(d); gs, sg = units.groups(c, fname); ch = False
        for i in sg:
            k = s.tr_single(c.val[i].decode('cp932'))
            if k is not None: c.val[i] = s.enc(k); ch = True
        for kind, idx in gs:
            vals = [c.val[j].decode('cp932') for j in idx]
            if kind == 'para':
                jp = ''.join(vals)
                if jp not in s.para: missing[jp] += 1; continue
                maxw = max(s.orig_width(v) for v in vals)
                new = wrap(s.enc, s.para[jp], len(idx), maxw)
                for j, v in zip(idx, new): c.val[j] = s.enc(v)
                ch = True
            else:
                jp = '¶'.join(vals)
                if jp not in s.lines: missing[jp] += 1; continue
                new = s.lines[jp].split('¶')
                if len(new) != len(idx): warn.append('줄 수 불일치: ' + jp[:30]); continue
                for j, v in zip(idx, new): c.val[j] = s.enc(v)
                ch = True
        return c.build() if ch else d

    def orig_width(s, v):
        # 원문 폭: 전각 25, 반각은 원본 폰트 폭
        w = 0
        for chh in v:
            b = chh.encode('cp932')
            w += ADV if len(b) == 2 else s.enc.w.get(b[0], 12)
        return w

    def xml(s, d, fname):
        txt = d
        def rep_block(m):
            blk = m.group(0)
            vals = [x.group(1).decode('cp932') for x in re.finditer(rb'<s\d\d>([^<>]*)</s\d\d>', blk)]
            jp = '¶'.join(vals)
            if jp in s.lines:
                new = s.lines[jp].split('¶')
                if len(new) == len(vals):
                    it = iter(new)
                    return re.sub(rb'(<s\d\d>)([^<>]*)(</s\d\d>)', lambda x: x.group(1) + s.enc(next(it)) + x.group(3), blk)
            return blk
        if fname.lower().startswith(('tips', 'directions')):
            return re.sub(rb'<string>.*?</string>', rep_block, txt, flags=re.S)
        # 주석(<? ?>)은 건드리지 않고 태그 사이 텍스트만
        parts = re.split(rb'(<\?.*?\?>)', txt, flags=re.S)
        for pi in range(0, len(parts), 2):
            def rep(m):
                t = m.group(2).decode('cp932'); st = t.strip()
                if st and units.JP.search(st) and not units.is_token(m.group(1).decode(), st):
                    k = s.tr_single(st)
                    if k is not None: return b'<' + m.group(1) + b'>' + s.enc(t.replace(st, k)) + b'</' + m.group(1) + b'>'
                return m.group(0)
            parts[pi] = re.sub(rb'<(\w+)>([^<>]*)</\1>', rep, parts[pi])
        return b''.join(parts)

    def episode(s, d):
        b = bytearray(d); n = struct.unpack_from('<I', d, 0)[0]
        for r in range(n):
            base = 4 + 0x200 * r
            for off, ln in [(0x80, 0x40), (0xc0, 0x80), (0x140, 0x80)]:
                t = d[base + off:base + off + ln].split(b'\0')[0].decode('cp932')
                if not t or not units.JP.search(t): continue
                k = s.tr_single(t)
                if k is None: continue
                e = s.enc(k)
                if len(e) >= ln: warn.append('에피소드 넘침: ' + k); e = e[:ln - 1]
                b[base + off:base + off + ln] = e + b'\0' * (ln - len(e))
        return bytes(b)


# ---------------------------------------------------------------- 이미지
def load_images():
    p = os.path.join(ROOT, 'work', 'img_out', 'map.json')
    if not os.path.exists(p): return {}
    m = json.load(open(p, encoding='utf-8'))
    out = {}
    for k, v in m.items():
        out[k] = (open(os.path.join(ROOT, v[0]), 'rb').read(), open(os.path.join(ROOT, v[1]), 'rb').read())
    return out


# ---------------------------------------------------------------- 트리 패치
def patch_tree(d, path, tp, imgs):
    fname = path.split('/')[-1]; e = fname.rsplit('.', 1)[-1].lower()
    if d[:4] == b'PACK':
        p = PACK(d); ch = False
        names = p.names
        for i, (nm, x) in enumerate(zip(names, p.data)):
            if nm.endswith('pixel.gs'):
                base = nm[:-8]
                if base + 'palette.gs' in names:
                    pal = p.data[names.index(base + 'palette.gs')]
                    h = hashlib.md5(x + pal).hexdigest()
                    if h in imgs:
                        p.data[i] = imgs[h][0]; p.data[names.index(base + 'palette.gs')] = imgs[h][1]; ch = True; log['img'] += 1
                continue
            if nm.endswith('palette.gs'): continue
            nx = patch_tree(x, path + '/' + nm, tp, imgs)
            if nx != x: p.data[i] = nx; ch = True
        return p.build() if ch else d
    if e == 'cxm': log['cxm'] += 1; return tp.cxm(d, fname)
    if e == 'xml': log['xml'] += 1; return tp.xml(d, fname)
    if fname == 'collection_episode.bin': log['episode'] += 1; return tp.episode(d)
    return d


def patch_elf(elf_tr, enc):
    d = bytearray(open(os.path.join(ROOT, 'extract', 'SLPS_258.81'), 'rb').read())
    slots = {int(l.split('\t')[0], 16): int(l.split('\t')[1]) for l in open(os.path.join(TR, 'src', 'elf.tsv'), encoding='utf-8').read().splitlines()}
    for off, (jp, ko) in elf_tr.items():
        if ko == jp or ko == '=': continue
        orig = jp.replace('\\n', '\n').encode('cp932')
        if d[off:off + len(orig)] != orig: warn.append('ELF 원문 불일치 %x' % off); continue
        b = enc(ko.replace('\\n', '\n'))
        if len(b) > slots[off] - 1: warn.append('ELF 넘침 %x %s' % (off, ko)); continue
        d[off:off + slots[off]] = b + b'\0' * (slots[off] - len(b))
        log['elf'] += 1
    return bytes(d)


# ---------------------------------------------------------------- 메인
def main(out=OUT_ISO):
    t0 = time.time()
    single, lines, para, elf_tr = load_tr()
    # 한글 문자 집합
    ks = [bytes([a, b]).decode('cp949') for a in range(0xb0, 0xc9) for b in range(0xa1, 0xff)]
    used = set()
    for dct in (single, lines, para):
        for v in dct.values(): used |= set(v)
    for jp, ko in elf_tr.values(): used |= set(ko)
    extra = sorted(c for c in used if ('가' <= c <= '힣' or 'ㄱ' <= c <= 'ㆎ') and c not in set(ks))
    korean = ks + extra
    # 남길 한자(스태프 인명·커맨드 기호)
    keep_txt = [jp for jp, ko in single.items() if ko == '='] + ['打組必']
    keep = set()
    for t in keep_txt:
        for ch in t:
            b = ch.encode('cp932', 'ignore')
            if len(b) == 2 and ((b[0] << 8) | b[1]) >= 0x889F: keep.add((b[0] << 8) | b[1])
    rep = {}
    cm = None
    for idx, fn in [(248, 'collection_font'), (249, 'font')]:
        src = open(os.path.join(ROOT, 'extract', 'afs', 'font', fn + '.pft'), 'rb').read()
        o, cm = build_font.build(src, korean, os.path.join(ROOT, 'SeoulHangangEB.ttf'), 25, 26, keep=keep)
        rep[idx] = o
    p = PFT(rep[249]); widths = {c: sum(p.width(i)) for c, i in p.codes().items()}
    enc = Enc(cm, widths)
    tp = TextPatcher(single, lines, para, enc)
    imgs = load_images()
    # AFS 순회
    f = open(afs.ISO, 'rb'); n, ent = afs.table(f); nm = afs.names()
    for i in range(n):
        top = nm[i].split('\\')[0]
        if top in ('voice', 'bgm', 'movie', 'se', 'effect', 'stage', 'font'): continue
        name = nm[i].replace('\\', '/')
        if not (name.endswith(('.cxm', '.xml', '.bin', '.gs'))): continue
        d = afs.read(f, ent, i)
        if name.endswith('pixel.gs') or name.endswith('palette.gs'): continue
        nd = patch_tree(d, f'{i}:{name}', tp, imgs)
        if nd != d: rep[i] = nd
    # 독립 .gs (mode_select 등)
    pairs = {}
    for i in range(n):
        if nm[i].endswith('pixel.gs'): pairs[nm[i][:-8]] = [i, None]
    for i in range(n):
        if nm[i].endswith('palette.gs') and nm[i][:-10] in pairs: pairs[nm[i][:-10]][1] = i
    for b, (pi, li) in pairs.items():
        if li is None: continue
        x = afs.read(f, ent, pi); pal = afs.read(f, ent, li)
        h = hashlib.md5(x + pal).hexdigest()
        if h in imgs: rep[pi], rep[li] = imgs[h]; log['img'] += 1
    f.close()
    elf = patch_elf(elf_tr, enc)
    build_iso.build(out, rep, {'/SLPS_258.81': elf})
    print('패치:', dict(log), 'AFS 교체', len(rep), '%.0fs' % (time.time() - t0))
    if missing:
        print('번역 없음', len(missing))
        with open(os.path.join(ROOT, 'work', 'missing.txt'), 'w', encoding='utf-8') as w:
            for k, v in missing.most_common(): w.write(f'{v}\t{k}\n')
    if warn:
        print('경고', len(warn))
        with open(os.path.join(ROOT, 'work', 'warn.txt'), 'w', encoding='utf-8') as w: w.write('\n'.join(warn))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else OUT_ISO)
