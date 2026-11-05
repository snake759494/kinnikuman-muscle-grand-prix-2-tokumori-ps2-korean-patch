"""번역 단위 추출 → translation/src/{single,lines,para}.tsv"""
import sys, os, re, collections, struct, glob
sys.path.insert(0, os.path.dirname(__file__))
import tree, units
from cxml import CXML
ROOT = os.path.join(os.path.dirname(__file__), '..')
single = collections.OrderedDict(); lines = collections.OrderedDict(); para = collections.OrderedDict()

def cat_of(path):
    p = path.lower()
    for k in ['commandlist', 'specialweapon', 'collection_explain', 'collection_episode', 'tips', 'staffroll',
              'practice', 'mode_tournament', 'scene_30', 'param_', 'char', 'directions', 'game_archive', 'mode_collection']:
        if k in p: return k
    return 'misc'

def add(dct, t, key, path):
    e = dct.setdefault(t, {'n': 0, 'keys': collections.Counter(), 'path': path})
    e['n'] += 1; e['keys'][key] += 1

def cb(path, d):
    e = path.rsplit('.', 1)[-1].lower(); fname = path.split('/')[-1]
    if e == 'cxm':
        c = CXML(d); gs, sg = units.groups(c, fname)
        for i in sg: add(single, c.val[i].decode('cp932'), c.name[i].decode(), path)
        for k, idx in gs:
            vals = [c.val[j].decode('cp932') for j in idx]
            if k == 'para': add(para, ''.join(vals), 'para', path)
            else: add(lines, '¶'.join(vals), 'lines', path)
    elif e == 'xml':
        body = re.sub(rb'<\?.*?\?>', b'', d, flags=re.S)
        if fname.lower().startswith(('tips', 'directions')):
            for blk in re.finditer(rb'<string>(.*?)</string>', body, flags=re.S):
                vals = [m.group(1).decode('cp932') for m in re.finditer(rb'<s\d\d>([^<>]*)</s\d\d>', blk.group(1))]
                if any(units.JP.search(v) for v in vals): add(lines, '¶'.join(vals), 'lines', path)
            return
        for m in re.finditer(rb'<(\w+)>([^<>]*)</\1>', body):
            t = m.group(2).decode('cp932').strip(); key = m.group(1).decode()
            if t and units.JP.search(t) and not units.is_token(key, t): add(single, t, 'xml:' + key, path)
    elif fname == 'collection_episode.bin':
        n = struct.unpack_from('<I', d, 0)[0]
        for r in range(n):
            b = 4 + 0x200 * r
            for off, ln, k in [(0x80, 0x40, 'ep_title'), (0xc0, 0x80, 'ep_sub'), (0x140, 0x80, 'ep_name')]:
                s = d[b + off:b + off + ln].split(b'\0')[0].decode('cp932')
                if s and units.JP.search(s): add(single, s, k, path)

if __name__ == '__main__':
    tree.walk(cb)
    for p in glob.glob(os.path.join(ROOT, 'extract', 'afs', 'xml', '**', '*.xml'), recursive=True):
        cb('xml/' + os.path.basename(p), open(p, 'rb').read())
    os.makedirs(os.path.join(ROOT, 'translation', 'src'), exist_ok=True)
    for name, dct in [('single', single), ('lines', lines), ('para', para)]:
        with open(os.path.join(ROOT, 'translation', 'src', name + '.tsv'), 'w', encoding='utf-8') as w:
            for t, e in dct.items():
                w.write('\t'.join([t.replace('\n', '\n'), cat_of(e['path']), ','.join(sorted(e['keys']))[:60], str(e['n'])]) + '\n')
        print(name, len(dct), sum(len(t) for t in dct))
