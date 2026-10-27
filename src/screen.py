"""Steps 1-2. Keyword screening and the exclusion filter.

Screening score  = sum of the weights (1-4) of the distinct dictionary terms present in a unit,
                   after variant normalization (data/screening_dictionary.csv).
Candidate        = clinical-chapter unit (Naegyeong, Oehyeong, Japbyeong) with score >= threshold.
Exclusion filter = exclusion terms of Table 1 (data/exclusion_terms.csv), variant-normalized,
                   plus the Paediatrics section (小兒). A blood term preceded by 唾/咯 (sputum)
                   or directly by a negation (無/不) is not counted.
"""
import re

from common import load_config, norm, read_csv


def load_dictionary(cfg=None):
    cfg = cfg or load_config()
    rows = read_csv(cfg["screening"]["dictionary"])
    return [dict(r, norm=norm(r["term"]), weight=int(r["weight"])) for r in rows]


def load_exclusions(cfg=None):
    cfg = cfg or load_config()
    out = {}
    for r in read_csv(cfg["screening"]["exclusion_terms"]):
        out.setdefault(r["category"], []).append(norm(r["term"]))
    return out


def _blood_hit(text, blood_terms):
    rx = re.compile("|".join(map(re.escape, blood_terms)))
    for m in rx.finditer(text):
        pre = text[max(0, m.start() - 2):m.start()]
        if re.search("[唾咯]", pre) or re.search("[無不]$", pre):
            continue
        return True
    return False


def exclusion_categories(u, excl, paediatric_section):
    t = u["norm"]
    cats = []
    for c, terms in excl.items():
        if c == "bloody_purulent_stool":
            if _blood_hit(t, terms):
                cats.append(c)
        elif any(x in t for x in terms):
            cats.append(c)
    if u["BB"].replace(" ", "") == paediatric_section:
        cats.append("paediatric_section")
    return cats


def score_unit(u, dictionary):
    hits = [d for d in dictionary if d["norm"] in u["norm"]]
    return sum(d["weight"] for d in hits), hits


def screen(units, cfg=None):
    cfg = cfg or load_config()
    D = load_dictionary(cfg)
    X = load_exclusions(cfg)
    thr = cfg["screening"]["threshold"]
    ped = cfg["screening"]["paediatric_section"]
    rows = []
    for u in units:
        if u["chapter_class"] != "clinical":
            continue
        s, hits = score_unit(u, D)
        cats = exclusion_categories(u, X, ped) if s >= thr else []
        rows.append(dict(unit_id=u["unit_id"], score=s, terms="|".join(h["term"] for h in hits),
                         candidate=s >= thr, excluded_by_filter=bool(cats),
                         exclusion_categories="|".join(cats)))
    return rows
