"""Statements: body passages divided at their source citations (researcher decision 2026-10-09).

A Donguibogam body passage usually strings together excerpts from several sources, each closed by its source
in 《…》. A body passage among the adjudication candidates that contains two or more such statements is
adjudicated statement by statement: statement k is the text up to and including its k-th citation, and any
text after the last citation forms a final statement of its own. Prescription entries are not divided.

Statement ids are "<unit_id>#<k>". A statement unit is a copy of its passage unit with the statement text,
so every later step (herb mentions, formula references, sections) works on statements unchanged.
"""
import re

from common import norm

CIT = re.compile(r"(《[^》]{1,12}》)")


def split_text(text):
    parts, buf = [], ""
    for piece in CIT.split(text or ""):
        buf += piece
        if CIT.fullmatch(piece):
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return parts


def is_split(unit):
    return unit["type"] == "body" and len(split_text(unit["text"])) >= 2


def statement_units(unit):
    """Statement units of a passage, or [] when the passage is not divided."""
    if not is_split(unit):
        return []
    out = []
    for k, t in enumerate(split_text(unit["text"]), 1):
        s = dict(unit)
        s.update(unit_id=f"{unit['unit_id']}#{k}", text=t, norm=norm(t), norm_text=norm(t), parent=unit["unit_id"],
                 statement_no=k)                           # body units have no name, so norm == norm_text
        out.append(s)
    return out


def decision_ids(cands, units_by_id):
    """Ids that receive an adjudication decision, in order: statements for divided passages, else the passage."""
    out = []
    for uid in cands:
        st = statement_units(units_by_id[uid])
        out.extend(s["unit_id"] for s in st) if st else out.append(uid)
    return out


def parent_of(decision_id):
    return decision_id.split("#")[0]


def reduced_units(included_ids, units_by_id):
    """Passages as the herb analysis counts them: one unit per passage with included text, in order. A divided
    passage keeps only its included source units, joined in order (each ends with its source mark, so no
    formula name or herb is read across a boundary); passage counts therefore stay counts of passages."""
    order, parts = [], {}
    for did in included_ids:
        p = parent_of(did)
        if p not in parts:
            order.append(p)
            parts[p] = []
        parts[p].append(did)
    out = []
    for p in order:
        u = units_by_id[p]
        if parts[p] == [p]:
            out.append(u)
            continue
        sts = [unit_of(d, units_by_id) for d in parts[p]]
        r = dict(u)
        if len(sts) < len(statement_units(u)):
            t = " ".join(s["text"] for s in sts)
            r.update(text=t, norm=norm(t), norm_text=norm(t))
        r["included_units"] = "|".join(str(s["statement_no"]) for s in sts)
        out.append(r)
    return out


def unit_of(decision_id, units_by_id):
    """The unit a decision id stands for: a statement unit for "<unit_id>#<k>", else the passage unit."""
    u = units_by_id[parent_of(decision_id)]
    if "#" not in decision_id:
        return u
    return statement_units(u)[int(decision_id.split("#")[1]) - 1]


CIT_ANY = re.compile(r"《[^》]{1,30}》")


def split_translation(text, translation):
    """The translation divided like split_text(text), or None when its source marks do not line up.

    Translators keep each source mark (《入門》) where the original has it. A mark inside a sentence
    (《內經》에 이르기를 …) is a reference, not a boundary, so only marks followed by a space or the end count.
    """
    if not translation:
        return None
    marks = [m for m in CIT_ANY.finditer(translation)
             if m.end() == len(translation) or translation[m.end()].isspace()]
    if [m.group(0) for m in marks] != CIT.findall(text or ""):
        return None
    parts, last = [], 0
    for m in marks:
        parts.append(translation[last:m.end()].strip())
        last = m.end()
    if translation[last:].strip():
        parts.append(translation[last:].strip())
    return parts if len(parts) == len(split_text(text)) else None


def translation_of(decision_id, units_by_id, translations):
    """Translation of a passage, or the matching part of its passage translation for a statement ("" if none)."""
    uid = parent_of(decision_id)
    t = translations.get(uid, "")
    if "#" not in decision_id:
        return t
    parts = split_translation(units_by_id[uid]["text"], t)
    return parts[int(decision_id.split("#")[1]) - 1] if parts else ""
