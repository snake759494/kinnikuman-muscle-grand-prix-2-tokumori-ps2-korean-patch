"""재빌드 준비: 원본 ISO → extract/ 추출, 원문 목록(translation/src) 생성,
공개 번역(translation/pub, 원문 해시)을 빌드용 번역(translation/ko, fix.tsv)으로 복원.
사용: python tools/prepare.py   (작업 폴더에 원본 ISO가 있어야 함)"""
import os, sys, glob, hashlib, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import afs, isopatch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TR = os.path.join(ROOT, 'translation')
H = lambda t: hashlib.sha1(t.encode('utf-8')).hexdigest()[:16]


def extract():
    os.chdir(ROOT)
    os.makedirs('extract', exist_ok=True)
    if not os.path.exists('extract/filelist.tsv'):   # DATA.BIN(AFS) 항목 이름 목록
        import shutil; shutil.copy('tools/filelist.tsv', 'extract/filelist.tsv')
    f = open(afs.ISO, 'rb')
    for p, (pos, lba, size) in isopatch.walk(f).items():
        if p.upper() == '/DATA.BIN': continue
        f.seek(lba * 2048); o = os.path.join('extract', p.lstrip('/'))
        os.makedirs(os.path.dirname(o), exist_ok=True); open(o, 'wb').write(f.read(size))
    afs.dump(lambda i, n: n.split(chr(92))[0] in ('font', 'xml'))
    # translation/src/elf.tsv(오프셋·슬롯 크기)는 저장소에 들어 있고, 원문은 ELF에서 읽는다.
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'extract_text.py')], check=True)


def restore():
    src = {}
    for n in ('single', 'lines', 'para'):
        for l in open(os.path.join(TR, 'src', n + '.tsv'), encoding='utf-8').read().splitlines():
            t = l.split('\t')[0]; src[H(t)] = t
    elf = open(os.path.join(ROOT, 'extract', 'SLPS_258.81'), 'rb').read()
    for l in open(os.path.join(TR, 'src', 'elf.tsv'), encoding='utf-8').read().splitlines():
        o = int(l.split('\t')[0], 16)
        t = elf[o:elf.index(b'\0', o)].decode('cp932').replace('\n', chr(92) + 'n'); src[H(t)] = t
    os.makedirs(os.path.join(TR, 'ko'), exist_ok=True)
    miss = 0
    for fn in glob.glob(os.path.join(TR, 'pub', '*.tsv')):
        name = os.path.basename(fn); out = []
        for l in open(fn, encoding='utf-8').read().splitlines()[1:]:
            i, h, ko = l.split('\t')
            if h not in src: miss += 1; continue
            out.append('\t'.join([i, src[h], ko]))
        if name == 'fix.tsv':
            body = '# 검수 수정: 원문\t번역\n' + ''.join(r.split('\t', 1)[1] + '\n' for r in out)
            open(os.path.join(TR, 'fix.tsv'), 'w', encoding='utf-8', newline='\n').write(body)
        else:
            body = 'id\tjp\tko\n' + ''.join(r + '\n' for r in out)
            open(os.path.join(TR, 'ko', name), 'w', encoding='utf-8', newline='\n').write(body)
    print('restored; missing =', miss)


if __name__ == '__main__':
    if '--restore-only' not in sys.argv: extract()
    restore()
