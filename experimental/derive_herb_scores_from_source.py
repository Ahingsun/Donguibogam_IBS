import os, re, glob, json, sys

def norm(s, vmap):
    for a,b in vmap.items(): s=s.replace(a,b)
    return s

def build(data_dir, cfg):
    vmap=cfg['variant_map']; axes=cfg['efficacy_axes']
    tonic=cfg['tonification_terms']; merid=cfg['meridian_targets']
    herbs={}; mustuse={}
    for f in sorted(glob.glob(os.path.join(data_dir,'동의보감_탕액편_*.txt'))):
        cur=None; buf=[]; subcat=None
        def flush():
            nonlocal cur,buf
            if cur and buf:
                herbs.setdefault(cur,{'name':cur,'text':''})
                herbs[cur]['text'] += ' '+' '.join(buf)
            buf=[]
        for raw in open(f,encoding='utf-8'):
            if raw.startswith('//') or not raw.strip(): continue
            p=raw.rstrip('\n').split('\t',1)
            if len(p)!=2: continue
            tag,text=p[0].strip(),norm(p[1].strip(),vmap)
            if tag=='CC': subcat=text; flush(); cur=None; continue
            if tag in ('CH','DP'):
                flush()
                # herb head: hanja token(s) before any space/Korean gloss
                m=re.match(r'([㐀-鿿]+)',text.replace('唐','').strip())
                cur=m.group(1) if m else None
                continue
            if tag=='SS' and cur:
                buf.append(text)
            # must-use: 諸經引導 lines "症狀, 須用 herbA, herbB"
            if subcat and '諸經引導' in subcat and '須用' in text:
                sym=text.split('須用')[0].strip(' ,，')
                for h in re.findall(r'[㐀-鿿]{2,}', text.split('須用',1)[1]):
                    mustuse.setdefault(h,[]).append(sym)
        flush()
    # annotate efficacy/meridian/tonify per herb
    for h,d in herbs.items():
        t=d['text']
        d['nature']=re.findall(r'性([㐀-鿿])',t)[:1]
        d['flavor']=re.findall(r'味([㐀-鿿]+)',t)[:1]
        d['efficacy']=[ax for ax,kws in axes.items() if any(k in t for k in kws)]
        d['meridians']=[m for m in merid if ('入'+m in t or '歸'+m in t or m+'經' in t)]
        d['tonifying']=any(k in t for k in tonic)
    return herbs, mustuse

if __name__=='__main__':
    dd=sys.argv[1]; cfg=json.load(open('data/config.json'))
    herbs,mustuse=build(dd,cfg)
    json.dump(herbs,open('results/herb_db.json','w'),ensure_ascii=False)
    json.dump(mustuse,open('results/must_use.json','w'),ensure_ascii=False)
    print('herbs extracted:',len(herbs))
    print('must-use herbs:',len(mustuse), '->', dict(list(mustuse.items())[:8]))
    for h in ['木香','厚朴','白朮','芍藥','肉豆蔲','黃連']:
        if h in herbs:
            d=herbs[h]; print(f'  {h}: nature={d["nature"]} flavor={d["flavor"]} eff={d["efficacy"]} merid={d["meridians"]} tonify={d["tonifying"]}')
        else: print(f'  {h}: NOT FOUND')
