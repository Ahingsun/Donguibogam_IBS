"""Herb lexicon: alias normalization, herb mentions in passages, prescription compositions and doses.

Counting rules
--------------
* Aliases are matched longest-first on the normalized text, so that 白附子 is not read as 附子
  and 靑橘皮 is not read as 橘皮. Aliases are at least two characters long (single-character
  mentions such as 薑 or 棗 are not counted, in line with the keyword rule).
* Names of prescriptions (DP/EP/CP names of three or more characters ending in a formula
  suffix, e.g. 湯 散 丸) are masked before counting, so herbs inside formula names
  (木香檳榔丸) are not counted.
* For a prescription unit, the unit name is counted only when the name itself is a herb
  (single-herb remedies, 單方).
* A herb name used to give a size (丸麻子大, 如雞子大, 大如雞子) is not a mention.
* Prescription compositions are built in composition.py.
"""
import re

from common import load_config, norm, read_csv


def load_aliases(cfg=None):
    cfg = cfg or load_config()
    rows = read_csv(cfg["herbs"]["aliases"])
    alias2canon, kind, meta = {}, {}, {}
    for r in rows:
        canon = norm(r["canonical"])
        kind[canon] = r["kind"]
        meta[canon] = r
        for a in r["aliases"].split("|"):
            a = norm(a.strip())
            if len(a) < 2:
                raise ValueError(f"alias shorter than 2 characters: {a} ({canon})")
            if a in alias2canon and alias2canon[a] != canon:
                raise ValueError(f"alias {a} assigned to both {alias2canon[a]} and {canon}")
            alias2canon[a] = canon
    rx = re.compile("|".join(map(re.escape, sorted(alias2canon, key=len, reverse=True))))
    return dict(alias2canon=alias2canon, kind=kind, meta=meta, rx=rx)


def formula_names(units, cfg=None):
    cfg = cfg or load_config()
    suf = tuple(cfg["herbs"]["formula_name_suffixes"])
    names = set()
    for u in units:
        if u["type"] == "presc" and u["name"]:
            n = norm(re.sub(r"\s+", "", u["name"]))
            if len(n) >= 3 and n.endswith(suf):
                names.add(n)
    return sorted(names, key=len, reverse=True)


class Masker:
    def __init__(self, names):
        self.rx = re.compile("|".join(map(re.escape, names))) if names else None

    def __call__(self, text):
        return self.rx.sub(lambda m: "□" * len(m.group(0)), text) if self.rx else text


SIZE_BEFORE = re.compile(r"(?:丸|如|似)\s*$")
SIZE_BEFORE_BIG = re.compile(r"大\s*(?:如|似)\s*$")


def is_size(text, m):
    """Pill or swelling size written with a herb name (丸麻子大, 如雞子大, 大如雞子) is not a mention."""
    before = text[max(0, m.start() - 3):m.start()]
    return bool((text[m.end():m.end() + 1] == "大" and SIZE_BEFORE.search(before)) or SIZE_BEFORE_BIG.search(before))


def mentions(text, lex):
    """Canonical herb names in order of appearance (one entry per mention)."""
    return [lex["alias2canon"][m.group(0)] for m in lex["rx"].finditer(text) if not is_size(text, m)]


def unit_mentions(u, lex, masker):
    t = masker(u["norm_text"])
    out = mentions(t, lex)
    if u["type"] == "presc" and u["name"]:
        n = norm(re.sub(r"\s+", "", u["name"]))
        if n in lex["alias2canon"]:                      # single-herb remedy (單方)
            out = [lex["alias2canon"][n]] + out
    return out


# ---------------------------------------------------------------- doses
NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100}
UNIT_FEN = {"斤": 1600.0, "兩": 100.0, "錢": 10.0, "分": 1.0, "字": 2.5, "銖": 100.0 / 24}
DOSE_RX = re.compile(r"(各)?\s*([一二三四五六七八九十百半]+)\s*(斤|兩|錢|分|字|銖|箇|个|枚|片|莖|握|升|合|匙|粒|條|撮|塊|盞|貼|丸)(半)?")


def chinese_number(s):
    if s == "半":
        return 0.5
    total, cur = 0, 0
    for ch in s:
        if ch == "半":
            total += 0.5
            continue
        v = NUM[ch]
        if v in (10, 100):
            total += (cur or 1) * v
            cur = 0
        else:
            cur = v
    return total + cur


def _dose_value(m):
    qty = chinese_number(m.group(2)) + (0.5 if m.group(4) else 0)
    unit = m.group(3)
    return qty * UNIT_FEN[unit] if unit in UNIT_FEN else None
