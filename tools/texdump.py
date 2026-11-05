"""모든 PACK/독립 .gs 텍스처를 PNG로 (중복 제거) + 접촉 시트"""
import sys, os, hashlib, re, json
sys.path.insert(0, os.path.dirname(__file__))
import tree, gs
from PIL import Image, ImageDraw
SKIP = ('gaugeFace', 'portrait', 'roundIcon', 'scene_10ext', 'testmenu')
def main(out='work/tex'):
    os.makedirs(out, exist_ok=True)
    seen = {}; pend = {}; items = []
    def cb(p, d):
        if any(s in p for s in SKIP): return
        if p.endswith('.gs'):
            base = p[:-len('pixel.gs')] if p.endswith('pixel.gs') else p[:-len('palette.gs')] if p.endswith('palette.gs') else None
            if base is None: return
            kind = 'pix' if p.endswith('pixel.gs') else 'pal'
            e = pend.setdefault(base, {}); e[kind] = d
            if 'pix' in e and 'pal' in e:
                h = hashlib.md5(e['pix'] + e['pal']).hexdigest()
                if h in seen: seen[h]['paths'].append(base); return
                try: idx, cols, psm = gs.load(e['pix'], e['pal'])
                except Exception as ex: return
                name = f'{len(seen):04d}'
                Image.fromarray(gs.rgba(idx, cols), 'RGBA').save(f'{out}/{name}.png')
                seen[h] = {'name': name, 'paths': [base], 'size': idx.shape[::-1]}
    tree.walk(cb)
    json.dump(list(seen.values()), open(f'{out}/index.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(len(seen))
if __name__ == '__main__': main()
