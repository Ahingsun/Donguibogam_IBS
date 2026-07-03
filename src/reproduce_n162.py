#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B: Deterministic reproduction of the final N=162 corpus and the published
Table-4 herb ranking, from the committed reproducibility artifacts:
  data/adjudication_339.xlsx        (per-passage keep/exclude adjudication; 162/177)
  data/herb_intrinsic_scores.csv    (75 corpus-independent points + n162 frequency)

Emits:
  results/n162_corpus.csv           the 162 included passages
  results/exclusions_177.csv        the 177 excluded passages (with rationale)
  results/table4_herb_ranking.csv   DGBG ranking (== manuscript Table 4)
Verifies every DGBG total against the committed CSV (must be 0 mismatches).
"""
import os, csv, math, openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def R(p): return os.path.join(ROOT, p)

def load_adjudication():
    wb = openpyxl.load_workbook(R('data/adjudication_339.xlsx'), read_only=True, data_only=True)
    ws = wb['01_전수판정_339']
    rows = list(ws.iter_rows(min_row=4, values_only=True))
    hdr = ['id','pyeon','mun','keywords','verdict','rationale','text']
    kept, excl = [], []
    for r in rows:
        if r[0] is None: continue
        rec = dict(zip(hdr, [(_ or '') for _ in r[:7]]))
        (kept if '유지' in str(rec['verdict']) else excl).append(rec)
    return kept, excl

def dgbg_ranking():
    herbs = []
    with open(R('data/herb_intrinsic_scores.csv'), encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            herbs.append(row)
    fmax = max(int(h['frequency_occurrence_n162']) for h in herbs)
    out, mism = [], 0
    for h in herbs:
        f = int(h['frequency_occurrence_n162'])
        fs = 25*math.log(1+f)/math.log(1+fmax)
        intrinsic = (float(h['efficacy25'])+float(h['meridian15'])+float(h['mustuse_seorye15'])
                     +float(h['pattern10'])+float(h['tonify10']))
        total = round(intrinsic+fs, 1)
        if abs(total-float(h['DGBG_total'])) > 0.15: mism += 1
        out.append({'herb':h['herb'],'DGBG':total,'freq_n162':f,'freq_score':round(fs,1),
                    'efficacy':h['efficacy25'],'meridian':h['meridian15'],
                    'mustuse_seorye':h['mustuse_seorye15'],'pattern':h['pattern10'],'tonify':h['tonify10']})
    out.sort(key=lambda d:-d['DGBG'])
    return out, fmax, mism

def main():
    kept, excl = load_adjudication()
    assert len(kept) == 162, f'expected 162 kept, got {len(kept)}'
    assert len(excl) == 177, f'expected 177 excluded, got {len(excl)}'

    with open(R('results/n162_corpus.csv'),'w',newline='',encoding='utf-8-sig') as fo:
        w=csv.DictWriter(fo,fieldnames=['id','pyeon','mun','keywords','verdict','rationale','text']); w.writeheader()
        for r in kept: w.writerow(r)
    with open(R('results/exclusions_177.csv'),'w',newline='',encoding='utf-8-sig') as fo:
        w=csv.DictWriter(fo,fieldnames=['id','pyeon','mun','keywords','verdict','rationale','text']); w.writeheader()
        for r in excl: w.writerow(r)

    ranking, fmax, mism = dgbg_ranking()
    with open(R('results/table4_herb_ranking.csv'),'w',newline='',encoding='utf-8-sig') as fo:
        w=csv.DictWriter(fo,fieldnames=list(ranking[0].keys())); w.writeheader()
        for d in ranking: w.writerow(d)

    print(f'Corpus:  included={len(kept)}  excluded={len(excl)}  total={len(kept)+len(excl)}')
    print(f'DGBG verification: {len(ranking)-mism}/{len(ranking)} herb totals reproduce committed CSV (mismatch={mism}); fmax={fmax}')
    print('\nTable 4 — Top-20 herbs by DGBG-IBS score:')
    for i,d in enumerate(ranking[:20],1):
        print(f'  {i:2d}. {d["herb"]:<4}  {d["DGBG"]:>5}   (freq_n162={d["freq_n162"]}, eff={d["efficacy"]}, 須用={d["mustuse_seorye"]})')

if __name__ == '__main__':
    main()
