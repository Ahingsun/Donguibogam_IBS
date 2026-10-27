"""Step 6. Prescription scores.

Prescription set
  recorded     : prescription entries (presc units) that are themselves final passages;
  recommended  : formulas named inside a final passage (e.g. 宜理中湯) whose entry lies elsewhere.
                 The entry is linked by name: the section named in a following 方見X cross-reference
                 if there is one, else the entry in the same section (門) as the recommending passage,
                 else the first entry in the clinical chapters (see referenced()).
Formulas with two or more constituents are ranked; single-herb remedies (單方 subsections, or one
constituent) are listed separately and not ranked.
Composition: composition.Composer (recipe segment, base formulas with 加/去/倍/同, cross-references,
herb named in the formula name); vehicles excluded; constituents outside the curated alias list are
kept as unscored ("other").

score_zero    (primary, as in the original analysis) mean over all constituents; a constituent
              outside the scored herb universe counts as 0.
score_scored  mean over constituents inside the herb universe only.
score_dose    dose-weighted mean over constituents inside the universe, when every such
              constituent has a convertible dose (兩 錢 分 字 銖 斤); otherwise not computed.
Bowel habit and patterns of a formula are those of the passage(s) that record or recommend it.
"""
import re

from common import norm


def _name(u):
    return norm(re.sub(r"\s+", "", u["name"]))


HINT_RX = re.compile(r"\s*方見(上|下|[^\s,.，。ㆍ]{1,4}?)(?:門|(?=[\s,.，。ㆍ]))")


def referenced(final_units, formula_list, composer):
    """Entries of formulas recommended by name in final passages.
    Link order: the section named in a following 方見X (上/下 = the nearest entry above/below in the
    same volume), else the entry in the passage's own section, else the first clinical entry."""
    rx = re.compile("|".join(map(re.escape, formula_list))) if formula_list else None
    refs = {}
    for u in final_units:
        own = _name(u) if u["type"] == "presc" else ""
        for m in rx.finditer(u["norm_text"]):
            n = m.group(0)
            if n == own or n not in composer.entries:
                continue
            xm = HINT_RX.match(u["norm_text"][m.end():m.end() + 8])
            pick = composer.resolve(n, u, xm.group(1)) if xm else None
            if pick is None:
                pick = next((e for e in composer.entries[n] if e["BB"] == u["BB"] and e["unit_id"] != u["unit_id"]), None)
            if pick is None:
                pick = composer.entries[n][0]
            r = refs.setdefault(pick["unit_id"], dict(entry=pick, recommended_in=set()))
            r["recommended_in"].add(u["unit_id"])
    return refs


def prescription_table(final_units, all_units, composer, herb_scores, annotations, formula_list):
    final_ids = {u["unit_id"] for u in final_units}
    items = {}
    for u in final_units:
        if u["type"] == "presc":
            items[u["unit_id"]] = dict(entry=u, source="recorded in an IBS passage", passages={u["unit_id"]})
    for uid, r in referenced(final_units, formula_list, composer).items():
        if uid in items:
            items[uid]["passages"] |= r["recommended_in"]
            continue
        items[uid] = dict(entry=r["entry"], source="recommended in an IBS passage", passages=set(r["recommended_in"]))
    rows = []
    for uid, it in items.items():
        u = it["entry"]
        raw, how = composer.composition(u)
        comp = [(h, d) for h, d in raw if composer.kind.get(h) in ("herb", "other")]
        if not comp:
            continue
        scored = [(h, d) for h, d in comp if h in herb_scores]
        s_zero = sum(herb_scores.get(h, 0.0) for h, _ in comp) / len(comp)
        s_scored = (sum(herb_scores[h] for h, _ in scored) / len(scored)) if scored else 0.0
        s_dose = ""
        if scored and all(d is not None for _, d in scored):
            tot = sum(d for _, d in scored)
            s_dose = sum(herb_scores[h] * d for h, d in scored) / tot if tot else ""
        habits = sorted({annotations[p]["bowel_habit"] for p in it["passages"] if p in annotations})
        core = any(annotations[p].get("tier") == 1 for p in it["passages"] if p in annotations)
        pats = sorted({x for p in it["passages"] if p in annotations for x in annotations[p]["patterns"].split("|") if x})
        single = (u["CC"].replace(" ", "") == "單方") or len(comp) < 2
        rows.append(dict(
            unit_id=uid, prescription=u["name"], source=it["source"],
            entry_section=f"{u['BB']}/{u['CC']}/{u['DD']}".rstrip("/"),
            ibs_passages="|".join(sorted(it["passages"])), n_constituents=len(comp), n_scored=len(scored),
            constituents="|".join(f"{h}" + (f"({d:g}分)" if d is not None else "") for h, d in comp),
            unscored="|".join(h for h, _ in comp if h not in herb_scores),
            composition_note=how,
            score_zero=round(s_zero, 2), score_scored=round(s_scored, 2),
            score_dose=round(s_dose, 2) if s_dose != "" else "",
            bowel_habit="|".join(habits), patterns="|".join(pats),
            kind="single-herb remedy" if single else "formula", in_final_passages="yes" if uid in final_ids else "",
            from_tier1_unit="yes" if core else ""))
    multi = sorted([r for r in rows if r["kind"] == "formula"], key=lambda r: (-r["score_zero"], r["prescription"]))
    single = sorted([r for r in rows if r["kind"] != "formula"], key=lambda r: (-r["score_zero"], r["prescription"]))
    for i, r in enumerate(multi, 1):
        r["rank_overall"] = i
    for r in single:
        r["rank_overall"] = ""
    return multi + single


def stratified(rows, key, k=5):
    out = []
    groups = {}
    for r in rows:
        if r.get("kind") != "formula":
            continue
        vals = r[key].split("|") if r[key] else ["(none)"]
        for v in vals:
            groups.setdefault(v, []).append(r)
    for g in sorted(groups):
        for i, r in enumerate(sorted(groups[g], key=lambda r: (-r["score_zero"], r["prescription"]))[:k], 1):
            out.append(dict(stratum_type=key, stratum=g, rank_in_stratum=i, prescription=r["prescription"],
                            source=r["source"], score_zero=r["score_zero"], score_scored=r["score_scored"],
                            score_dose=r["score_dose"], rank_overall=r["rank_overall"], unit_id=r["unit_id"],
                            n_in_stratum=len(groups[g])))
    return out
