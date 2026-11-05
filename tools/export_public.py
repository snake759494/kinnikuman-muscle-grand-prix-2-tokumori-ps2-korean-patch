"""translation/ko, fix.tsv → translation/pub (원문 대신 SHA-1 앞 16자리)."""
import os, glob, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TR = os.path.join(ROOT, 'translation')
H = lambda t: hashlib.sha1(t.encode('utf-8')).hexdigest()[:16]
os.makedirs(os.path.join(TR, 'pub'), exist_ok=True)
for fn in glob.glob(os.path.join(TR, 'ko', '*.tsv')):
    rows = [l.split('\t')[:3] for l in open(fn, encoding='utf-8').read().splitlines()[1:] if l]
    open(os.path.join(TR, 'pub', os.path.basename(fn)), 'w', encoding='utf-8', newline=chr(10)).write(
        'id\tsrc_sha1_16\tko\n' + ''.join(f'{i}\t{H(jp)}\t{ko}\n' for i, jp, ko in rows))
rows = [l.split('\t') for l in open(os.path.join(TR, 'fix.tsv'), encoding='utf-8').read().splitlines() if l and not l.startswith('#')]
open(os.path.join(TR, 'pub', 'fix.tsv'), 'w', encoding='utf-8', newline=chr(10)).write(
    'id\tsrc_sha1_16\tko\n' + ''.join(f'fix_{n:03d}\t{H(a)}\t{b}\n' for n, (a, b) in enumerate(rows)))
