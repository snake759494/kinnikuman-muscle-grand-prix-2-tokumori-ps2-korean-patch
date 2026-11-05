"""글자 이미지 한글화: 원본 글자의 외곽선색·채움 그라데이션을 추출해 같은 스타일로 한글을 다시 그린다.
사양: translation/images.tsv  (이름\t한글\t옵션 JSON)
출력: work/img_out/*.gs + map.json(원본 pixel+palette md5 → 새 파일), 미리보기 work/img_out/preview/*.png"""
import sys, os, json, hashlib, struct
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import gs, tree, afs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FONTS = {'heavy': 'NanumSquareNeo-eHv.ttf', 'bold': 'NanumSquareNeo-dEb.ttf', 'myeong': 'SeoulHangangEB.ttf',
         'myeongB': 'SeoulHangangB.ttf', 'gal': 'work/galmuri/Galmuri11-Bold.ttf', 'gal11': 'work/galmuri/Galmuri11.ttf', 'gal9': 'work/galmuri/Galmuri9.ttf'}


def read_specs():
    out = []
    for l in open(os.path.join(ROOT, 'translation', 'images.tsv'), encoding='utf-8').read().splitlines():
        if not l.strip() or l.startswith('#'): continue
        a = l.split('\t')
        opt = json.loads(a[2]) if len(a) > 2 and a[2].strip() else {}
        out.append((a[0], a[1].replace('\\n', '\n'), opt))
    return out


def collect(names):
    """이름별 (pixel, palette) 원본 변종들"""
    want = set(names); got = {}
    pend = {}
    def cb(p, d):
        if not p.endswith('.gs'): return
        fn = p.split('/')[-1]
        for suf, k in (('pixel.gs', 0), ('palette.gs', 1)):
            if fn.endswith(suf):
                b = fn[:-len(suf)]
                if b in want:
                    key = p[:-len(suf)]
                    e = pend.setdefault(key, [None, None]); e[k] = d
                    if e[0] is not None and e[1] is not None:
                        h = hashlib.md5(e[0] + e[1]).hexdigest()
                        got.setdefault(b, {})[h] = (e[0], e[1])
    tree.walk(cb)
    return got


# ---------------------------------------------------------------- 렌더링
def text_mask(text, font, size, sx=1.0, spacing=0, vert=False):
    f = ImageFont.truetype(os.path.join(ROOT, font), size)
    if vert:
        cells = []
        for ch in text:
            if ch == ' ': cells.append(np.zeros((size, size // 2), np.float32)); continue
            im = Image.new('L', (size * 2, size * 2)); ImageDraw.Draw(im).text((size, size), ch, font=f, fill=255, anchor='mm')
            a = np.array(im); ys, xs = np.where(a > 0)
            if len(ys) == 0: continue
            # 글자 칸: 세로 높이=가로폭 방향, 중심 정렬
            c = a[size - size // 2 - 2:size + size // 2 + 2, :]
            c = c[:, xs.min():xs.max() + 1]
            c = np.rot90(c, 1)
            cells.append(c.astype(np.float32) / 255); cells.append(np.zeros((c.shape[0], max(1, size // 8)), np.float32))
        h = max(c.shape[0] for c in cells)
        cells = [np.pad(c, (((h - c.shape[0]) // 2, h - c.shape[0] - (h - c.shape[0]) // 2), (0, 0))) for c in cells]
        a = np.concatenate(cells, 1)
        ys, xs = np.where(a > 0)
        return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    lines = text.split('\n')
    W = int(size * max(len(l) for l in lines) * 1.3 + 40); H = int(size * 1.4 * len(lines) + 40)
    im = Image.new('L', (W, H)); dr = ImageDraw.Draw(im)
    y = 20
    for l in lines:
        x = 20
        if spacing:
            for ch in l:
                dr.text((x, y), ch, font=f, fill=255); x += f.getlength(ch) + spacing
        else:
            dr.text((x, y), l, font=f, fill=255)
        y += int(size * 1.15)
    a = np.array(im)
    ys, xs = np.where(a > 0)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if sx != 1.0:
        a = cv2.resize(a, (max(1, int(a.shape[1] * sx)), a.shape[0]), interpolation=cv2.INTER_AREA)
    return a.astype(np.float32) / 255


def analyze(rgba, box):
    x0, y0, x1, y1 = box
    a = rgba[y0:y1, x0:x1]
    m = (a[..., 3] > 60).astype(np.uint8)
    if m.sum() == 0: return None
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    ys, xs = np.where(m > 0)
    bb = (xs.min() + x0, ys.min() + y0, xs.max() + 1 + x0, ys.max() + 1 + y0)
    md = dist.max()
    return {'mask': m, 'dist': dist, 'bbox': bb, 'maxd': md}


def style_of(rgba, info, sw):
    a = rgba[info['bbox'][1]:info['bbox'][3], info['bbox'][0]:info['bbox'][2]]
    x0, y0 = info['bbox'][0], info['bbox'][1]
    m = info['mask']; dist = info['dist']
    # info 좌표계(box)에서 bbox 좌표계로
    bx0, by0 = info['bbox'][0] - info['box'][0], info['bbox'][1] - info['box'][1]
    d = dist[by0:by0 + a.shape[0], bx0:bx0 + a.shape[1]]
    out_px = a[(d > 0) & (d <= sw)][:, :3]
    in_px = (d > sw)
    oc = np.median(out_px, 0) if len(out_px) else np.array([0, 0, 0])
    rows = []
    for y in range(a.shape[0]):
        r = a[y][in_px[y]][:, :3]
        rows.append(np.median(r, 0) if len(r) else None)
    # 비어있는 줄 보간
    good = [i for i, r in enumerate(rows) if r is not None]
    if not good:
        allin = a[d > 0][:, :3]; c = np.median(allin, 0); rows = [c] * a.shape[0]
    else:
        for i in range(len(rows)):
            if rows[i] is None:
                j = min(good, key=lambda g: abs(g - i)); rows[i] = rows[j]
    return oc, np.array(rows)


def render(rgba, text, opt):
    H, W = rgba.shape[:2]
    box = opt.get('box', [0, 0, W, H])
    info = analyze(rgba, box)
    info['box'] = box
    bx = info['bbox']
    th = bx[3] - bx[1]; tw = bx[2] - bx[0]
    sw = opt.get('sw', max(1, min(4, int(round(info['maxd'] * 0.45)))))
    oc, grad = style_of(rgba, info, sw)
    if 'outline' in opt: oc = np.array(opt['outline'], float)
    if 'fill' in opt:
        f = opt['fill']
        if isinstance(f[0], list):
            grad = np.array([np.array(f[0]) + (np.array(f[1]) - np.array(f[0])) * t for t in np.linspace(0, 1, th)])
        else: grad = np.array([f] * th, float)
    # 새 이미지: 영역 지우기
    out = rgba.astype(np.float32).copy()
    clr = opt.get('clear', box)
    if opt.get('bg') == 'inpaint':
        cm = np.zeros((H, W), np.uint8); cx0, cy0, cx1, cy1 = clr
        cm[cy0:cy1, cx0:cx1] = (rgba[cy0:cy1, cx0:cx1, 3] > 0) & opt.get('_textsel', True)
        sel = opt.get('inpaint_sel')
        if sel == 'dark':
            lum = rgba[..., :3].mean(2); cm[:] = 0; reg = lum[cy0:cy1, cx0:cx1] < opt.get('thr', 90); cm[cy0:cy1, cx0:cx1] = reg
        elif sel == 'bright':
            lum = rgba[..., :3].mean(2); cm[:] = 0; reg = lum[cy0:cy1, cx0:cx1] > opt.get('thr', 170); cm[cy0:cy1, cx0:cx1] = reg
        elif sel == 'color':
            ref = np.array(opt['ref'], float); dd = np.abs(rgba[..., :3].astype(float) - ref).sum(2)
            cm[:] = 0; cm[cy0:cy1, cx0:cx1] = dd[cy0:cy1, cx0:cx1] < opt.get('thr', 120)
        cm = cv2.dilate(cm, np.ones((3, 3), np.uint8), iterations=opt.get('dil', 2))
        rgb = cv2.inpaint(rgba[..., :3].copy(), cm, 5, cv2.INPAINT_TELEA)
        out[..., :3] = rgb
    elif opt.get('bg') == 'fill':
        cx0, cy0, cx1, cy1 = clr; out[cy0:cy1, cx0:cx1] = np.array(opt['bgcol'] + [255], float)
    else:
        cx0, cy0, cx1, cy1 = clr; out[cy0:cy1, cx0:cx1] = 0
    # 글자
    font = FONTS[opt.get('font', 'heavy')]
    tgt_h = opt.get('h', th - 2 * sw)
    area = opt.get('area', [bx[0], bx[1], bx[2], bx[3]])
    if opt.get('fit_box'): area = box
    maxw = area[2] - area[0] - 2 * sw
    size = 8; tm = None
    for s in range(6, 200):
        t2 = text_mask(text, font, s, spacing=opt.get('spacing', 0), vert=opt.get('vert', False))
        if t2.shape[0] > tgt_h: break
        size, tm = s, t2
    if tm is None: tm = text_mask(text, font, 6)
    sx = min(opt.get('sx', 1.0), maxw / tm.shape[1]) if tm.shape[1] > 0 else 1
    if sx < 1.0 or opt.get('sx'): tm = cv2.resize(tm, (max(1, int(tm.shape[1] * sx)), tm.shape[0]), interpolation=cv2.INTER_AREA)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * sw + 1, 2 * sw + 1))
    pad = sw + 1
    tmp = np.pad(tm, pad)
    ol = cv2.dilate(tmp, k)
    if opt.get('bold'):
        tmp = cv2.dilate(tmp, np.ones((2, 2), np.uint8)) * 0.6 + tmp * 0.4
    h2, w2 = tmp.shape
    # 그라데이션: 글자 높이에 맞춰 재샘플
    g = grad[np.clip((np.arange(h2) - pad) * len(grad) // max(1, h2 - 2 * pad), 0, len(grad) - 1)]
    col = np.zeros((h2, w2, 4), np.float32)
    col[..., :3] = oc
    col[..., :3] = col[..., :3] * (1 - tmp[..., None]) + g[:, None, :] * tmp[..., None]
    alpha = np.clip(ol if opt.get('outline', True) is not False else tmp, 0, 1)
    if opt.get('nooutline'): alpha = tmp; col[..., :3] = g[:, None, :]
    col[..., 3] = alpha * opt.get('alpha', 255)
    # 배치
    al = opt.get('align', 'center')
    if al == 'left': x = area[0] - pad + sw
    elif al == 'right': x = area[2] - w2 + pad - sw
    else: x = (area[0] + area[2]) // 2 - w2 // 2
    y = (area[1] + area[3]) // 2 - h2 // 2 + opt.get('dy', 0)
    x += opt.get('dx', 0)
    for yy in range(h2):
        for_y = y + yy
        if not (0 <= for_y < H): continue
        xs0 = max(0, x); xs1 = min(W, x + w2)
        if xs1 <= xs0: continue
        src = col[yy, xs0 - x:xs1 - x]; dst = out[for_y, xs0:xs1]
        a_ = src[:, 3:4] / 255
        dst[:, :3] = dst[:, :3] * (1 - a_) + src[:, :3] * a_
        dst[:, 3] = np.maximum(dst[:, 3], src[:, 3]) if opt.get('bg') != 'inpaint' else dst[:, 3]
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- 인코딩
def quantize(rgba, n):
    px = rgba.reshape(-1, 4).astype(np.float32)
    # 알파 0 은 하나로
    uniq = np.unique(px, axis=0)
    if len(uniq) <= n:
        cols = uniq
    else:
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        w = px.copy(); w[:, 3] *= 1.5
        _, lab, cen = cv2.kmeans(w, n - 1, None, crit, 2, cv2.KMEANS_PP_CENTERS)
        cen[:, 3] /= 1.5
        cols = np.vstack([[0, 0, 0, 0], cen])
    d = ((px[:, None, :] - cols[None, :, :]) ** 2 * np.array([1, 1, 1, 2])).sum(2)
    idx = d.argmin(1)
    cols = np.clip(np.round(cols), 0, 255).astype(np.uint8)
    if len(cols) < n: cols = np.vstack([cols, np.zeros((n - len(cols), 4), np.uint8)])
    return idx.reshape(rgba.shape[:2]).astype(np.uint8), cols


def encode(rgba, pix, pal):
    h = gs.hdr(pix); psm = h[1]
    n = 16 if psm == 0x14 else 256
    idx, cols = quantize(rgba, n)
    c = cols.astype(np.int32).copy(); c[:, 3] = (c[:, 3] + 1) // 2   # PS2 알파 0~0x80
    c = np.clip(c, 0, 255).astype(np.uint8)
    if n == 256:
        c = c.reshape(8, 2, 2, 8, 4).transpose(0, 2, 1, 3, 4).reshape(256, 4)
    newpal = bytearray(pal); newpal[0x80:0x80 + c.size] = c.tobytes()
    flat = idx.flatten()
    if psm == 0x14:
        body = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8).tobytes()
    else:
        body = flat.tobytes()
    newpix = bytearray(pix); newpix[0x80:0x80 + len(body)] = body
    return bytes(newpix), bytes(newpal)


def main(only=None):
    specs = read_specs()
    if only: specs = [s for s in specs if s[0] in only]
    got = collect([s[0] for s in specs])
    od = os.path.join(ROOT, 'work', 'img_out'); os.makedirs(od + '/preview', exist_ok=True)
    mp = os.path.join(od, 'map.json')
    m = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) and only else {}
    canon = {}
    for name, text, opt in specs:
        if opt.get('bymatch') and name in got:
            pix, pal = next(iter(got[name].values())); i_, c_, _ = gs.load(pix, pal)
            canon[name] = (gs.rgba(i_, c_).astype(np.int32), text)
    for name, text, opt in specs:
        if name not in got: print('없음', name); continue
        for h, (pix, pal) in got[name].items():
            idx, cols, psm = gs.load(pix, pal)
            rgba = gs.rgba(idx, cols)
            if opt.get('bymatch'):
                pre = opt['bymatch']; a = rgba.astype(np.int32)
                cands = [(np.abs(v[0] - a).mean(), v[1]) for k, v in canon.items() if k.startswith(pre) and v[0].shape == a.shape]
                text = min(cands)[1]
            if 'src' in opt:   # 다른 이미지의 원본 스타일 사용 안 함
                pass
            if opt.get('rot180'): rgba = np.ascontiguousarray(rgba[::-1, ::-1])
            new = render(rgba, text, opt) if text != '-' else rgba
            for t2, o2 in opt.get('extra', []): new = render(new, t2.replace(chr(92) + 'n', chr(10)), o2)
            if opt.get('rot180'): new = np.ascontiguousarray(new[::-1, ::-1]); rgba = np.ascontiguousarray(rgba[::-1, ::-1])
            if 'post' in opt: new = POST[opt['post']](new, rgba)
            np_, nl = encode(new, pix, pal)
            fp = f'work/img_out/{h}_pix.gs'; fl = f'work/img_out/{h}_pal.gs'
            open(os.path.join(ROOT, fp), 'wb').write(np_); open(os.path.join(ROOT, fl), 'wb').write(nl)
            m[h] = [fp, fl]
            # 미리보기 (재디코딩)
            i2, c2, _ = gs.load(np_, nl)
            prev = np.concatenate([rgba, gs.rgba(i2, c2)], 0)
            bg = np.zeros_like(prev); bg[..., :] = (60, 60, 100, 255)
            a = prev[..., 3:4] / 255.0; comp = (prev[..., :3] * a + bg[..., :3] * (1 - a)).astype(np.uint8)
            Image.fromarray(comp).save(f'{od}/preview/{name}.png')
    json.dump(m, open(mp, 'w', encoding='utf-8'), indent=0)
    print('이미지', len(m))

POST = {}

if __name__ == '__main__':
    main(set(sys.argv[1:]) or None)
