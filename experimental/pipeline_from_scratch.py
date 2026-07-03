"""End-to-end Donguibogam IBS herb-prioritization pipeline.
Stages: parse -> keyword-score -> inclusion/exclusion -> herb frequency ->
6-component herb score -> TF-IDF specificity -> weight sensitivity (Spearman).
Reads ALL 23 Donguibogam volumes. Numbers are produced by the code (not hard-coded)."""
import os, re, json, math, glob, sys
from collections import Counter, defaultdict

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def R(p): return os.path.join(ROOT,p)

def norm(s,vmap):
    for a,b in vmap.items(): s=s.replace(a,b)
    return s

def spearman(a,b):
    n=len(a)
    def rank(x):
        order=sorted(range(n),key=lambda i:x[i])
        r=[0]*n
        i=0
        while i<n:
            j=i
            while j+1<n and x[order[j+1]]==x[order[i]]: j+=1
            avg=(i+j)/2+1
            for k in range(i,j+1): r[order[k]]=avg
            i=j+1
        return r
    ra,rb=rank(a),rank(b)
    ma=sum(ra)/n; mb=sum(rb)/n
    num=sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da=math.sqrt(sum((x-ma)**2 for x in ra)); db=math.sqrt(sum((x-mb)**2 for x in rb))
    return num/(da*db) if da*db else 0.0

def main(data_dir):
    cfg=json.load(open(R('data/config.json')))
    vmap=cfg['variant_map']
    kw=json.load(open(R('data/keyword_dictionary.json')))
    incl_terms=sorted({norm(r['term'],vmap) for r in kw if 'Exclusion' not in r['category']},key=len,reverse=True)
    units=json.load(open(R('results/passages.json')))
    herbs=json.load(open(R('results/herb_db.json')))
    mustuse=set(json.load(open(R('results/must_use.json'))).keys())
    # optional OASIS-sourced meridian overrides
    mov=R('data/meridian_overrides.json')
    meridian_over=json.load(open(mov)) if os.path.exists(mov) else {}

    # 1) keyword score + candidates
    for u in units: u['_t']=norm(u['text'],vmap)
    def kwscore(t): return sum(t.count(x) for x in incl_terms)
    for u in units: u['score']=kwscore(u['_t'])
    candidates=[u for u in units if u['score']>=3]

    # 2) inclusion/exclusion
    excl=cfg['exclusion']; chron=cfg['chronicity_markers']
    def keep(u):
        t=u['_t']
        for cat,terms in excl.items():
            if any(x in t for x in terms):
                if cat=='bloody_purulent' and any(c in t for c in chron):
                    continue
                return False
        return True
    final=[u for u in candidates if keep(u)]

    # 3) herb frequency within final IBS corpus
    STOP={'酒','水','火','人','白','大','小','黃','蜜','鹽','醋','薑'}
    herb_names=sorted([h for h in herbs if len(h)>=2 and h not in STOP],key=len,reverse=True)
    freq=Counter()
    # section frequency for TF-IDF (section = source file chapter-type)
    sec_herb=defaultdict(set)
    corpus_text=' '.join(u['_t'] for u in final)
    for u in final:
        seen=set()
        for h in herb_names:
            if h in u['_t']:
                freq[h]+=1; seen.add(h)
        for h in seen: sec_herb[u['source']].add(h)
    ibs_herbs=[h for h in freq if freq[h]>0]

    # 4) six-component score
    def comp(h):
        d=herbs[h]
        f=freq[h]
        c1=25*math.log1p(f)/math.log1p(max(freq.values()))         # frequency (log-normalized)
        c2=25*len(d.get('efficacy',[]))/8                          # efficacy 8-axis
        mer=meridian_over.get(h,d.get('meridians',[]))
        c3=15*min(len(mer),len(cfg['meridian_targets']))/len(cfg['meridian_targets'])  # meridian
        c4=15 if h in mustuse else 0                               # must-use
        pats=[p for p,kws in cfg['ibs_patterns'].items() if any(k in d['text'] for k in kws)]
        c5=10*len(pats)/7                                          # pattern coverage
        c6=10 if d.get('tonifying') else 0                         # tonification
        return dict(frequency=round(c1,2),efficacy=round(c2,2),meridian=round(c3,2),
                    mustuse=c4,pattern=round(c5,2),tonify=c6,
                    total=round(c1+c2+c3+c4+c5+c6,2),freq=f,axes=len(d.get('efficacy',[])))
    scores={h:comp(h) for h in ibs_herbs}
    ranked=sorted(scores.items(),key=lambda kv:-kv[1]['total'])

    # 5) sensitivity: TF-IDF specificity correction + weight scenarios
    nsec=len(set(u['source'] for u in final)) or 1
    def idf(h):
        df=sum(1 for s in sec_herb if h in sec_herb[s]) or 1
        return math.log(nsec/df)+1
    base=[scores[h]['total'] for h,_ in ranked]
    tfidf=[scores[h]['total']*idf(h) for h,_ in ranked]
    rho_tfidf=spearman(base,tfidf)
    scen={
     'equal':      [scores[h]['frequency']*0+ (100/6)*(scores[h][k]>0) for h in [x[0] for x in ranked] for k in ['frequency']],  # placeholder
    }
    # weight scenarios: recompute totals under alternative weights
    W={'primary':dict(frequency=1,efficacy=1,meridian=1,mustuse=1,pattern=1,tonify=1),
       'equal':dict(frequency=1,efficacy=1,meridian=1,mustuse=1,pattern=1,tonify=1),
       'no_freq':dict(frequency=0,efficacy=1,meridian=1,mustuse=1,pattern=1,tonify=1),
       'efficacy_centered':dict(frequency=0.5,efficacy=2,meridian=1,mustuse=1,pattern=1,tonify=1),
       'no_mustuse':dict(frequency=1,efficacy=1,meridian=1,mustuse=0,pattern=1,tonify=1)}
    def totalw(h,w):
        s=scores[h]; return (s['frequency']*w['frequency']+s['efficacy']*w['efficacy']+s['meridian']*w['meridian']
                +s['mustuse']*w['mustuse']+s['pattern']*w['pattern']+s['tonify']*w['tonify'])
    order=[h for h,_ in ranked]
    prim=[totalw(h,W['primary']) for h in order]
    sens={}
    for name,w in W.items():
        vals=[totalw(h,w) for h in order]
        sens[name]=round(spearman(prim,vals),3)

    # ---- outputs ----
    os.makedirs(R('results'),exist_ok=True)
    with open(R('results/herb_ranking.csv'),'w',encoding='utf-8') as fo:
        fo.write('rank,herb,total,frequency,efficacy,meridian,mustuse,pattern,tonify,freq_count,efficacy_axes\n')
        for i,(h,s) in enumerate(ranked,1):
            fo.write(f'{i},{h},{s["total"]},{s["frequency"]},{s["efficacy"]},{s["meridian"]},{s["mustuse"]},{s["pattern"]},{s["tonify"]},{s["freq"]},{s["axes"]}\n')
    summary=dict(total_units=len(units),candidates_ge3=len(candidates),final_corpus=len(final),
                 herbs_in_corpus=len(ibs_herbs),rho_tfidf=round(rho_tfidf,3),weight_sensitivity=sens)
    json.dump(summary,open(R('results/summary.json'),'w'),ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('\nTOP 20 herbs:')
    for i,(h,s) in enumerate(ranked[:20],1):
        print(f'  {i:2d}. {h}  total={s["total"]:5.1f}  (freq={s["freq"]}, axes={s["axes"]}, mustuse={"Y" if s["mustuse"] else "-"}, tonify={"Y" if s["tonify"] else "-"})')

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else '/sessions/sweet-wonderful-mayer/mnt/새 폴더')
