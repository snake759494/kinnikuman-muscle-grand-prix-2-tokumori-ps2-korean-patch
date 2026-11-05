"""CXML/XML 값 → 번역 단위 분류 (추출과 빌드가 같은 규칙을 쓴다)."""
import re
JP = re.compile('[぀-ヿ一-鿿！-｠　-〿‐-♯]')
TOKENS = {'打', '組', '必', 'Ｇ', '・', '＋', '【', '】', 'G', '+'}
LINE = re.compile(r'^(s\d\d|explain_\d\d\d|index_\d\d\d)$')

def is_token(key, v):
    return key.startswith('command') and (v in TOKENS or v.isdigit())

def group_kind(fname, parent_path, key):
    """None | 'para' | 'lines'"""
    f = fname.lower()
    if not LINE.match(key): return None
    if 'collection_explain' in f and parent_path.endswith('/explain'): return 'para'
    if ('tips' in f and parent_path.endswith('/string')) : return 'lines'
    if 'practice' in f and key.startswith('explain_'): return 'lines'
    if 'direction' in f and key.startswith('s'): return 'lines'
    return None

def groups(c, fname):
    """CXML c 에서 그룹 단위 [(kind, [node idx...])] 와 단일 [idx] 반환"""
    par = {}
    singles = []
    for i, v in enumerate(c.val):
        if v is None: continue
        t = v.decode('cp932'); key = c.name[i].decode('cp932')
        if not JP.search(t) or is_token(key, t): continue
        pp = c.path(c.nodes[i][2])
        k = group_kind(fname, pp, key)
        if k: par.setdefault((k, c.nodes[i][2]), []).append(i)
        else: singles.append(i)
    gs = []
    for (k, p), idx in par.items():
        # 같은 부모의 모든 줄(일본어 없는 줄 포함) 정렬
        sib = sorted([j for j in range(len(c.nodes)) if c.nodes[j][2] == p and LINE.match(c.name[j].decode()) and c.val[j] is not None],
                     key=lambda j: c.name[j])
        gs.append((k, sib))
    return gs, singles
