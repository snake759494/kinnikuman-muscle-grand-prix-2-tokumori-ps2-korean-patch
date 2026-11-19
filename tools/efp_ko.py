"""이펙트(effect/*.efp) 안 그림 글자(초필살기 이름 띠, 풍림화산 한자 타일) 한글화.
translation/efp.tsv 의 대표 텍스처(파일_번호)와 픽셀이 같은 텍스처는 모든 의상판에서 함께 바꾼다."""
import os, sys, hashlib
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import efp, img_ko
ROOT = os.path.join(os.path.dirname(__file__), '..')
FONT = 'SeoulHangangEB.ttf'


def load_tr():
    out = {}
    for l in open(os.path.join(ROOT, 'translation', 'efp.tsv'), encoding='utf-8').read().splitlines():
        if not l or l.startswith('#'): continue
        k, v = l.split('\t'); out[k] = v
    return out


def tex_key(d, t):
    n = t['w'] * t['h'] if t['psm'] == 0x13 else t['w'] * t['h'] // 2
    return hashlib.md5(d[t['pix']:t['pix'] + n] + d[t['pal']:t['pal'] + 1024]).hexdigest()


def _mask(text, px, S=4):
    return img_ko.text_mask(text, FONT, px * S)


def render_banner(orig, text):
    """흰~크림 가운데·붉은 위아래 그라데이션 + 검은 외곽선(약 3px)."""
    H, W = orig.shape[:2]
    a = orig[..., 3] > 60
    ys, xs = np.where(a)
    x0 = xs.min() if len(xs) else 2
    S = 4; ow = 3
    fill_h = 26                                     # 원본 글자 몸통 높이(약 24px)
    m = img_ko.text_mask(text, FONT, 200)           # 큰 크기로 만든 뒤 줄인다
    sc = fill_h * S / m.shape[0]
    w4 = int(m.shape[1] * sc); h4 = fill_h * S
    maxw = (W - x0 - 2 * ow - 2) * S
    if w4 > maxw: w4 = maxw                          # 넘치면 가로로만 줄임
    m = cv2.resize(m, (w4, h4), interpolation=cv2.INTER_AREA)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))   # 원본 붓글씨만큼 굵게
    pad = (ow + 2) * S
    m = np.pad(m, pad)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ow * S + 1, 2 * ow * S + 1))
    ol = cv2.dilate(m, k)
    # 세로 그라데이션(글자 몸통 기준)
    stops = [(0.0, (196, 40, 32)), (0.30, (248, 150, 110)), (0.48, (252, 244, 220)),
             (0.62, (250, 214, 170)), (1.0, (214, 44, 36))]
    hh = m.shape[0]; g = np.zeros((hh, 3), np.float32)
    for y in range(hh):
        t = np.clip((y - pad) / max(1, h4 - 1), 0, 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0); g[y] = np.array(c0) * (1 - u) + np.array(c1) * u; break
    col = np.zeros(m.shape + (4,), np.float32)
    col[..., :3] = g[:, None, :] * m[..., None]           # 외곽선은 검정
    col[..., 3] = ol * 255
    small = cv2.resize(col, (col.shape[1] // S, col.shape[0] // S), interpolation=cv2.INTER_AREA)
    # 알파 프리멀티 → 직선 알파
    al = small[..., 3:4] / 255
    small[..., :3] = np.where(al > 0, small[..., :3] / np.maximum(al, 1e-3), 0)
    out = np.zeros((H, W, 4), np.float32)
    sh, sw = small.shape[:2]
    y = (H - sh) // 2 - 1
    x = max(0, x0 - ow - 2)
    sy, dy = max(0, -y), max(0, y)
    sw2 = min(sw, W - x); sh2 = min(sh - sy, H - dy)
    out[dy:dy + sh2, x:x + sw2] = small[sy:sy + sh2, :sw2]
    return np.clip(out, 0, 255).astype(np.uint8)


def render_tile(orig, text):
    """풍림화산 타일: 검은 바탕 흰 붓글씨, 알파 고정."""
    H, W = orig.shape[:2]
    lum = orig[..., :3].max(2) > 100
    ys, xs = np.where(lum)
    bh = ys.max() - ys.min() + 1
    m = img_ko.text_mask(text, FONT, 200)
    sc = bh / m.shape[0]
    m = cv2.resize(m, (max(1, int(m.shape[1] * sc)), bh), interpolation=cv2.INTER_AREA)
    m = cv2.dilate(m, np.ones((2, 2), np.uint8)) * 0.5 + m * 0.5
    out = orig.copy(); out[..., :3] = 0
    cy = (ys.min() + ys.max()) // 2; cx = W // 2
    y0 = cy - m.shape[0] // 2; x0 = cx - m.shape[1] // 2
    v = (np.clip(m, 0, 1) * 255).astype(np.uint8)
    for c in range(3): out[y0:y0 + m.shape[0], x0:x0 + m.shape[1], c] = v
    return out


def encode(d, t, rgba, keep_alpha=None):
    idx, cols = img_ko.quantize(rgba, 256)
    if keep_alpha is not None: cols[:, 3] = keep_alpha
    else: cols[:, 3] = (cols[:, 3].astype(int) * 128 + 127) // 255   # PS2 알파(0x80=불투명)
    c = efp.swz(cols.astype(np.uint8).reshape(256, 4))
    d[t['pal']:t['pal'] + 1024] = c.tobytes()
    d[t['pix']:t['pix'] + t['w'] * t['h']] = idx.astype(np.uint8).tobytes()


def patch(data, tr, keys):
    """data: efp bytes. keys: {해시: 한글}. 바뀐 개수와 새 bytes."""
    d = bytearray(data); n = 0
    for t in efp.textures(data):
        k = tex_key(data, t)
        if k not in keys: continue
        idx, c = efp.decode(data, t); orig = c[idx]
        text = keys[k]
        if t['h'] == 64:
            new = render_tile(orig, text); encode(d, t, new, keep_alpha=int(orig[..., 3].max()))
        else:
            new = render_banner(orig, text); encode(d, t, new)
        n += 1
    return bytes(d), n


def build_keys(read):
    """read(파일명) -> efp bytes.  대표 id → 해시."""
    tr = load_tr(); keys = {}
    for id_, ko in tr.items():
        fn, k = id_.rsplit('_', 1)
        d = read(fn); t = efp.textures(d)[int(k)]
        keys[tex_key(d, t)] = ko
    return keys
