import re
JP=re.compile('[぀-ヿ一-鿿！-｠　-〿]')
def scan(d, ranges=((0x1b4a00,0x32b024),(0x32b080,0x35e154),(0x35eb00,0x360e9a))):
    out=[]
    for a,b in ranges:
        i=a
        while i<b:
            if d[i]==0: i+=1; continue
            j=d.index(b'\0',i)
            s=d[i:j]
            try: t=s.decode('cp932')
            except UnicodeDecodeError: i=j+1; continue
            if JP.search(t) and all(c.isprintable() or c in '\n' for c in t):
                # 슬롯: 다음 비0 바이트까지
                k=j
                while k<b and d[k]==0: k+=1
                out.append((i,t,k-i))
            i=j+1
    return out
