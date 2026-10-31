"""Prescription compositions.

Rules
-----
* Recipe segment. The entry text before the preparation instruction, i.e. the first clause that
  starts with 右 followed by a count (右三味), a quantity word (右等分, 右各) or a preparation verb
  (右剉, 右爲末, 右以…). Agents added after it (ginger and jujube for decoctions, binders, coatings,
  optional additions such as 若加X名曰Y) are not constituents. An alternative recipe introduced by
  若加 / 一方 / 又方 inside the segment ends it.
* Base formula with modifications. When the recipe names another formula followed by 加 (add),
  去 (remove), 倍 (double the dose) or 同 (same as), the composition is that formula's composition with
  the modifications applied, e.g. 六柱散 = 四柱散 + 訶子, 肉豆蔲. Two or more formulas each followed by a
  dose form a mixture (union of compositions, doses not combined). Formula names in a clause containing
  名 (一名X, 名曰X) are alternative names, not base formulas.
* Cross-reference entries. An entry that names no herb before 方見X (e.g. 平胃散 in the Internal Damage
  section, 方見五藏) takes the composition of the entry of the same name in section X.
* Herb named in the formula name. A herb whose name is part of the formula name and that is mentioned
  in the entry is a constituent even when it is added during preparation (阿膠 in 黃連阿膠元).
* Recognition. Constituents are matched with the curated alias list and, in addition, with every
  Decoctions-chapter entry name of two or more characters, so that a constituent outside the curated
  list is counted (as unscored, kind "other") rather than silently dropped.
* Processing notes. Text in parentheses (小字 notes such as 黃連(以吳茱萸煎水浸炒)) names processing
  agents, not constituents, and is ignored.
* Doses. A dose written right after a herb, or after a group of herbs (各), is converted to 分.
"""
import re

from common import norm
from lexicon import DOSE_RX, _dose_value, is_size

PREP_RX = re.compile(r"(?:^|(?<=[\s.,，。、)）》]))右\s*(?:[一二三四五六七八九十]+\s*味|"
                     r"[剉銼爲細搗㕮麤麄粗同件藥和入將末作以水各等幷並共用取酒醋蜜煎煮擣硏炒焙])")
VARIANT_RX = re.compile(r"若加|一方|又方")
OP_RX = re.compile(r"加|去|倍")
NUMQ = r"[一二三四五六七八九十百半]+\s*(?:斤|兩|錢|分)"
TRIG_RX = re.compile(
    r"^(?:\s|[,，ㆍ]|本方|原方|一劑|一料|一貼|方見(?P<hint>[^\s,.，。]{1,4}?)(?:門|上|下|(?=[\s,.，。]))|" + NUMQ + r")*?"
    r"(?:(?P<op>加|去|倍|同)|(?P<dose>" + NUMQ + r"))")
PROC_CHARS = "炒煨灸製細末炮蒸焙酒醋鹽浸洗去皮"
PAREN_RX = re.compile(r"[(（][^)）]*[)）]")


def _mask_notes(text):
    return PAREN_RX.sub(lambda m: "□" * len(m.group(0)), text)
SECTION_MAP = {"藏": "臟", "府": "腑"}


def _section_match(hint, bb):
    h = "".join(SECTION_MAP.get(c, c) for c in hint)
    return bool(h) and h in bb.replace(" ", "")


def _name(u):
    return norm(re.sub(r"\s+", "", u["name"]))


class Composer:
    def __init__(self, units, lex, masker, formula_list, tangaek_names):
        self.lex, self.masker = lex, masker
        self.frx = re.compile("|".join(map(re.escape, formula_list))) if formula_list else None
        self.entries = {}
        self.presc = [u for u in units if u["type"] == "presc" and u["name"] and u["chapter_class"] == "clinical"]
        fl = set(formula_list)
        for u in units:
            if u["type"] == "presc" and u["name"] and u["chapter_class"] == "clinical":
                n = _name(u)
                if n in fl:
                    self.entries.setdefault(n, []).append(u)
        self.canon = dict(lex["alias2canon"])
        self.kind = dict(lex["kind"])
        for n in tangaek_names:
            if len(n) >= 2 and n not in self.canon:
                self.canon[n] = n
                self.kind.setdefault(n, "other")
        self.rx = re.compile("|".join(map(re.escape, sorted(self.canon, key=len, reverse=True))))
        self.cache = {}

    # ------------------------------------------------------------------ helpers
    def resolve(self, name, ref, hint=None, direction=None):
        """Entry of formula `name` referred to from unit `ref`. direction 'above'/'below' (上X, 方見上/下)
        means the nearest entry in the same volume, before/after `ref`, whose name ends with `name`."""
        if hint in ("上", "下"):
            direction, hint = ("above" if hint == "上" else "below"), None
        if direction:
            near = [e for e in self.presc if e["book"] == ref["book"] and e["unit_id"] != ref["unit_id"]
                    and _name(e).endswith(name)]
            if direction == "above":
                near = [e for e in near if e["line_start"] < ref["line_start"]]
                if near:
                    return max(near, key=lambda e: e["line_start"])
            else:
                near = [e for e in near if e["line_start"] > ref["line_start"]]
                if near:
                    return min(near, key=lambda e: e["line_start"])
        cands = [e for e in self.entries.get(name, []) if e["unit_id"] != ref["unit_id"]]
        if hint:
            pick = next((e for e in cands if _section_match(hint, e["BB"])), None)
            if pick is None:       # the passage may name the formula in a short or variant form
                pick = next((e for e in self.presc if _section_match(hint, e["BB"]) and _name(e).endswith(name)
                             and e["unit_id"] != ref["unit_id"]), None)
            if pick:
                return pick
        if not cands:
            return None
        return next((e for e in cands if e["BB"] == ref["BB"]), cands[0])

    def _herbs_with_doses(self, seg, ops=None):
        """(canonical, dose, op) for herbs in a masked segment. `ops`: list of (pos, op)."""
        items, pending, pos = [], [], 0
        for mm in self.rx.finditer(seg):
            if is_size(seg, mm):
                continue
            between = seg[pos:mm.start()]
            d = DOSE_RX.search(between)
            if d and pending:
                dose = _dose_value(d)
                items.extend((h, dose, op) for h, op in pending)
                pending = []
            op = None
            if ops:
                prev = [o for p, o in ops if p < mm.start()]
                op = prev[-1] if prev else None
            pending.append((self.canon[mm.group(0)], op))
            pos = mm.end()
        d = DOSE_RX.search(seg[pos:pos + 12])
        dose = _dose_value(d) if d else None
        items.extend((h, dose, op) for h, op in pending)
        return items

    def _segment(self, text):
        m = PREP_RX.search(text)
        seg = text[:m.start()] if m else text
        first = self.rx.search(self.masker(seg))
        if first:
            v = VARIANT_RX.search(seg, first.end())
            if v:
                seg = seg[:v.start()]
        return seg

    def _base_refs(self, seg, own):
        refs = []
        if not self.frx:
            return refs
        for m in self.frx.finditer(seg):
            n = m.group(0)
            if n == own:
                continue
            cut = max(seg.rfind(p, 0, m.start()) for p in ".,，。、")
            if "名" in seg[cut + 1:m.start()]:
                continue
            t = TRIG_RX.match(seg[m.end():m.end() + 20])
            if not t:
                continue
            op, end = t.group("op"), m.end() + t.end()
            if not op:                                   # dose first, then 加/去/倍 (益元散 三兩, 加紅麴)
                a = re.match(r"^[\s,，]*(?:[(（][^)）]*[)）])?[\s,，]*(加|去|倍)", seg[end:end + 12])
                if a:
                    op, end = a.group(1), end + a.end()
            bd = re.search(NUMQ, t.group(0))
            refs.append(dict(start=m.start(), end=m.end(), name=n, op=op or "mix", hint=t.group("hint"),
                             base_dose=_dose_value(DOSE_RX.search(bd.group(0))) if bd else None,
                             above=seg[max(0, m.start() - 1):m.start()] == "上", trig_end=end))
        return refs

    # ------------------------------------------------------------------ main
    def composition(self, u, _stack=None):
        """List of (canonical, dose_fen or None) and a note describing how it was obtained."""
        uid = u["unit_id"]
        if uid in self.cache:
            return self.cache[uid]
        stack = (_stack or set()) | {uid}
        own = _name(u)
        text = u["norm_text"]
        note = []
        seg = self._segment(text)
        masked = _mask_notes(self.masker(seg))
        # cross-reference entry: no herb before 方見X
        xm = re.search(r"方見(\S{1,4}?)(?:門|上|下|(?=[\s,.，。]))", seg)
        if xm and not self.rx.search(_mask_notes(self.masker(seg[:xm.start()]))) and not self._base_refs(seg[:xm.start()], own):
            tgt = self.resolve(own, u, xm.group(1))
            if tgt is not None and tgt["unit_id"] not in stack:
                comp, sub = self.composition(tgt, stack)
                out = (comp, f"cross-reference to {tgt['BB']} ({tgt['unit_id']})")
                self.cache[uid] = out
                return out
        refs = self._base_refs(seg, own)
        comp = []
        if refs:
            mods_from = max(r["trig_end"] for r in refs) - 1
            for r in refs:
                tgt = self.resolve(r["name"], u, r["hint"], "above" if r["above"] else None)
                if tgt is None or tgt["unit_id"] in stack:
                    note.append(f"base {r['name']} not resolved")
                    continue
                bc, _ = self.composition(tgt, stack)
                if r["op"] == "mix":
                    bc = [(h, None) for h, _ in bc]
                elif r["base_dose"] and all(d is not None for _, d in bc) and sum(d for _, d in bc) > 0:
                    k = r["base_dose"] / sum(d for _, d in bc)          # base used in a stated amount
                    bc = [(h, d * k) for h, d in bc]
                comp.extend(bc)
                note.append(("mixture with " if r["op"] == "mix" else "base ") + f"{r['name']} ({tgt['unit_id']})")
            # herbs written before the first base reference are ordinary constituents
            pre = self._herbs_with_doses(masked[:refs[0]["start"]])
            comp = [(h, d) for h, d, _ in pre] + comp
            ops = [(m.start(), m.group(0)) for m in OP_RX.finditer(masked, mods_from)]
            ops = [(mods_from, "加")] + ops if refs[-1]["op"] in ("加", "mix") else [(mods_from, refs[-1]["op"])] + ops
            post = self._herbs_with_doses(masked[mods_from:], [(p - mods_from, o) for p, o in ops])
            names = [h for h, _ in comp]
            for h, d, op in post:
                if op == "去":
                    comp = [(x, dd) for x, dd in comp if x != h]
                    note.append(f"minus {h}")
                elif op == "倍":
                    comp = [(x, (dd * 2 if (x == h and dd is not None) else dd)) for x, dd in comp]
                    note.append(f"double {h}")
                elif op == "同":
                    continue
                elif h not in names:
                    comp.append((h, d))
                    names.append(h)
                    note.append(f"plus {h}")
        else:
            comp = [(h, d) for h, d, _ in self._herbs_with_doses(masked)]
        # herb named in the formula name, mentioned only outside the recipe segment
        have = {h for h, _ in comp}
        for a, c in self.lex["alias2canon"].items():
            if a in own and c not in have and self.kind.get(c) == "herb":
                i = text.find(a)
                if i >= 0:
                    tail = text[i + len(a):i + len(a) + 10].lstrip(PROC_CHARS + " ()（）")
                    d = DOSE_RX.match(tail)
                    comp.append((c, _dose_value(d) if d else None))
                    have.add(c)
                    note.append(f"named herb {c}")
        if not comp and u["name"] and own in self.canon:          # single-herb remedy
            comp = [(self.canon[own], None)]
        seen, out = set(), []
        for h, d in comp:
            if h not in seen:
                seen.add(h)
                out.append((h, d))
        res = (out, "; ".join(note))
        self.cache[uid] = res
        return res
