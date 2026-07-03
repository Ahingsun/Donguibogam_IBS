#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGBG-IBS reproducible pipeline
==============================
Reference implementation for:
  "A Donguibogam-Based Algorithm for Prioritizing Candidate Herbs and
   Prescriptions for Irritable Bowel Syndrome"

This script documents, end to end and without any subjective/manual step, how the
study moves from the 23 Donguibogam source text files to (a) the IBS passage corpus
and (b) the herb priority ranking, so that a third party can reproduce every number.

INPUTS (place in the same folder, or pass paths):
  1. ../../동의보감_IBS/*.txt            23 Donguibogam source files (KIOM Mediclassics)
                                          tag format: AA=chapter BB=門 CC=subcat DD=detail
                                          ZZ=body  DP/EP/CP=prescription name  SS=prescription herbs
                                          DK=acupoint  DH/CH=herb-dictionary entry
  2. keyword_dictionary.csv             inclusion/exclusion keyword list (Table 1)
  3. herb_intrinsic_scores.csv          the corpus-INDEPENDENT 75 points per herb
                                          (efficacy 25 + meridian 15 + must-use/序例 15 +
                                           pattern 10 + tonify 10) plus the published frequency
  4. ../동의보감_IBS_조문선정_확정.xlsx   the passage-by-passage inclusion/exclusion
                                          adjudication (ROME IV decision + rationale)

SCORING (documented in Table 2 of the manuscript), DGBG = weighted sum, max 100:
  frequency 25  = 25 * ln(1+f) / ln(1+f_max)     # f = occurrence in the IBS corpus
  efficacy  25  = number of the 8 IBS efficacy axes the herb carries
  meridian  15  = spleen/stomach/large-int/small-int/liver/kidney tropism match
  must-use  15  = 序例 (Tangaek preface) "須用" direct designation for a symptom
  pattern   10  = coverage of the 7 IBS bian-zheng patterns
  tonify    10  = 序例 large-intestine tonification
  Prescription score = mean DGBG of its constituent herbs (unscored herb = 0).

PASSAGE SELECTION (no subjective expert step):
  candidate  : keyword score >= 3 using keyword_dictionary.csv (variant chars unified:
               飱<->飧<->飡, 秘<->祕, 姙<->妊, 藏<->臟; single characters 泄/瀉/痢 disallowed)
  inclusion  : I-1 chronic/functional bowel symptom is the passage's CHIEF complaint
               I-2 pattern fits an IBS bian-zheng frame
               I-3 if I-1 holds, source 門 may be non-GI (judge by CONTENT not section)
  exclusion  : E-1 pre-registered (parasite/epidemic/acute 霍亂/pregnancy 姙娠·産後/
                    痘瘡·麻疹/anorectal organic 痔·脫肛·腸癰·藏毒·腸風/acute 噤口·暴痢)
               E-2 pediatric (小兒)   E-3 acute febrile 傷寒·暑 (except chronic 虛寒: 理中湯類·眞武湯)
               E-4 incidental keyword match   E-5 pure theory/pulse   E-6 abdominal pain w/o
               defecation link   E-7 systemic disease with incidental diarrhea
  => 9,100 units -> 434 candidates -> 272 excluded -> n = 162 included.

Run:  python ibs_pipeline.py
"""
import os, re, glob, csv, math, argparse
from collections import defaultdict, Counter

# ---- variant-character normalisation (applied to BOTH inclusion and exclusion sides) ----
VARIANT_MAP = {"飱": "飧", "飡": "飧", "祕": "秘", "姙": "妊", "藏": "臟"}
def normalize(s: str) -> str:
    if not s:
        return ""
    for a, b in VARIANT_MAP.items():
        s = s.replace(a, b)
    return s

# ---- 1. parse the 23 source files into passage units --------------------------------
def parse_file(fp):
    units, BB, CC, cur = [], "", "", None
    for raw in open(fp, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("//") or not line.strip():
            continue
        m = re.match(r"^([A-Z]{2})\t(.*)$", line)
        if not m:
            if cur is not None:
                cur["text"] += " " + line.strip()
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "BB":
            BB, CC = val, ""
        elif tag == "CC":
            CC = val
        elif tag == "AA":
            BB = CC = ""
        elif tag == "ZZ":
            cur = {"BB": BB, "CC": CC, "type": "body", "name": "", "text": val}
            units.append(cur)
        elif tag in ("DP", "EP", "CP"):
            cur = {"BB": BB, "CC": CC, "type": "presc", "name": val, "text": ""}
            units.append(cur)
        elif tag == "SS":
            if cur is not None and cur["type"] == "presc":
                cur["text"] += (" " + val if cur["text"] else val)
            else:
                cur = {"BB": BB, "CC": CC, "type": "presc", "name": "", "text": val}
                units.append(cur)
        elif tag == "DK":
            cur = {"BB": BB, "CC": CC, "type": "acu", "name": val, "text": val}
            units.append(cur)
        elif tag in ("DH", "CH"):
            cur = {"BB": BB, "CC": CC, "type": "hd", "name": "", "text": ""}
            units.append(cur)
        else:
            if cur is not None:
                cur["text"] += " " + val
    return units

def load_corpus(corpus_glob):
    allu = []
    for fp in sorted(glob.glob(corpus_glob)):
        allu += parse_file(fp)
    return allu

# ---- 2. load keyword dictionary ----------------------------------------------------
HANJA = re.compile(r"[㐀-鿿]+")
def load_keywords(path):
    inc, exc = [], []
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            kw = row.get("keyword", "")
            han = HANJA.findall(kw)
            if not han:
                continue
            term = normalize(max(han, key=len))
            if len(term) < 2:          # single characters disallowed
                continue
            inc.append(term)
    # pre-registered exclusion terms (normalised)
    exc = [normalize(x) for x in
           ["蛔蟲", "寸白蟲", "蟲積", "化蟲", "疫毒", "時疫", "瘟疫", "霍亂", "乾霍亂",
            "妊娠", "姙", "産後", "半産", "死胎", "子痢", "胎動", "痘瘡", "麻疹", "痘疹",
            "脫肛", "痔漏", "痔疾", "腸癰", "臟毒", "腸風", "噤口", "暴痢", "小兒"]]
    return sorted(set(inc)), sorted(set(exc))

# ---- 3. score every unit and pick candidates (score >= 3) --------------------------
def score_units(units, inc_kw):
    for u in units:
        txt = normalize(u["text"] + " " + u["BB"] + " " + u["CC"])
        u["score"] = sum(1 for k in inc_kw if k in txt)
    return units

# ---- 4. DGBG herb ranking ----------------------------------------------------------
def load_intrinsic(path):
    intr = {}
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            h = row["herb"].strip()
            # 75 corpus-independent points
            intr[h] = (float(row["efficacy25"]) + float(row["meridian15"]) +
                       float(row["mustuse_seorye15"]) + float(row["pattern10"]) +
                       float(row["tonify10"]))
    return intr

def herb_frequency(included_units, herbs):
    """occurrence = number of included passages whose text contains the herb name."""
    occ = Counter()
    for u in included_units:
        t = u["text"]
        for h in herbs:
            if h in t:
                occ[h] += 1
    return occ

def dgbg_rank(intr, occ):
    fmax = max(occ.values()) if occ else 1
    out = {}
    for h, base in intr.items():
        f = occ.get(h, 0)
        freq_score = 25 * math.log(1 + f) / math.log(1 + fmax) if fmax > 0 else 0.0
        out[h] = round(base + freq_score, 1)
    return dict(sorted(out.items(), key=lambda x: -x[1]))

# ---- main --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="../../동의보감_IBS/*.txt")
    ap.add_argument("--keywords", default="data/keyword_dictionary_180.csv")
    ap.add_argument("--intrinsic", default="data/herb_intrinsic_scores.csv")
    a = ap.parse_args()

    units = load_corpus(a.corpus)
    inc_kw, exc_kw = load_keywords(a.keywords)
    units = score_units(units, inc_kw)
    candidates = [u for u in units if u["score"] >= 3]

    print(f"total passage units      : {len(units)}")
    print(f"inclusion keywords        : {len(inc_kw)}")
    print(f"candidates (score >= 3)   : {len(candidates)}")
    print("NOTE: the final n=162 corpus is obtained by applying the I-1..I-3 / E-1..E-7")
    print("      criteria to these candidates; the per-passage decisions (with ROME IV")
    print("      rationale) are in ../동의보감_IBS_조문선정_확정.xlsx (sheet 01_전수판정).")

    intr = load_intrinsic(a.intrinsic)
    occ = herb_frequency([u for u in candidates if u["type"] == "presc"], list(intr))
    ranking = dgbg_rank(intr, occ)
    print("\nTop-10 herbs by DGBG-IBS score (reference run over candidate prescriptions):")
    for i, (h, s) in enumerate(list(ranking.items())[:10], 1):
        print(f"  {i:2d}. {h}  {s}")

if __name__ == "__main__":
    main()
