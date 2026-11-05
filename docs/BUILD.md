# 재빌드

## 준비
- Python 3, `pip install numpy Pillow opencv-python`
- 저장소 최상위에 원본 `Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan).iso`(MD5 `0aa259a64cf6414b5eb95111c5688414`)와 글꼴(`docs/FONT_CREDITS.md`)
- xdelta3 (`xdelta.exe`)

## 빌드
```powershell
python tools/prepare.py     # 원본 ISO에서 extract/ 추출, 원문 목록 생성, 번역 복원(translation/ko, fix.tsv)
python tools/img_ko.py      # 그림 글자 → work/img_out
python tools/build.py       # → "Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan) [KO].iso"
```
`prepare.py`는 `translation/pub/*.tsv`의 원문 해시를 원본에서 뽑은 문자열과 맞춰 빌드용 번역 파일을 만듭니다. "missing = 0"이 나와야 합니다. 번역을 고친 뒤에는 `python tools/export_public.py`로 `translation/pub`을 다시 만듭니다.

## 차분 파일
```powershell
.\xdelta.exe -e -0 -S none -A -s "Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan).iso" "Kinnikuman - Muscle Grand Prix 2 - Tokumori (Japan) [KO].iso" Kinnikuman_MGP2_Tokumori_PS2_KO_v1.1.xdelta
```

## 파일
- `translation/pub/s1~s4.tsv`: `ID	원문 SHA-1 앞 16자리	번역` (s1~s3 단일 문자열, s4의 `L_` 여러 줄 설명·`E_` 실행파일 문자열)
- `translation/pub/p1~p4.tsv`: 컬렉션 기술 해설 문단, `fix.tsv`: 검수 수정
- `translation/images.tsv`: 그림 글자 이름·한글·그리기 옵션(JSON)
- `translation/src/elf.tsv`: 실행파일 문자열 위치·칸 크기
- `tools/build.py`: 전체 빌드, `build_font.py`·`pft.py` PFNT 글꼴, `cxml.py` CXML, `pack.py` PACK, `gs.py` 텍스처, `img_ko.py` 그림 글자, `afs.py`·`build_iso.py`·`isopatch.py` 디스크, `extract_text.py`·`units.py`·`tree.py` 문자열 추출
- `tools/emu.py`, `sheets.py`, `texdump.py`: 검증·조사용 스크립트(개인 환경용)
- `SLPS-25881_9395CBE2.pnach`: 16:9 와이드 패치
