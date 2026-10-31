"""Run the whole R1 re-analysis from the 23 source texts and the curated tables in data/.

    python run_all.py

Outputs go to outputs/ (regenerated on every run). The researcher workbook in decisions/ is created
on the first run and only read afterwards. Re-running with unchanged inputs reproduces every number.
Without the workbook, the decisions are read from the adjudication record (decisions/adjudication_record.csv),
which every run with the workbook rewrites. config "outputs.source_text": false leaves the source text out of
the outputs.
"""
import copy
import csv
import datetime
import json
import os
import platform
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402

import acupoints  # noqa: E402
import adjudication  # noqa: E402
import figures  # noqa: E402
import sensitivity as sens  # noqa: E402
import statements  # noqa: E402
import stats  # noqa: E402
from annotate import annotate, load_patterns  # noqa: E402
from common import load_config, md5, norm, path, read_csv, sha256, write_csv  # noqa: E402
from corpus import parse, source_manifest  # noqa: E402
from composition import Composer  # noqa: E402
from features import herb_features, load_meridian_sources, score, tangaek_entries  # noqa: E402
from lexicon import Masker, formula_names, load_aliases, unit_mentions  # noqa: E402
from prescriptions import prescription_table, stratified  # noqa: E402
from screen import load_dictionary, screen  # noqa: E402

OUT = path("outputs")
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s)


def out(name):
    return os.path.join(OUT, name)


def main():
    cfg = load_config()
    keep_text = cfg.get("outputs", {}).get("source_text", True)

    def strip(rows, cols=("text",)):
        """rows without the columns that quote the source text, when the configuration leaves the text out"""
        return rows if keep_text else [{k: v for k, v in r.items() if k not in cols} for r in rows]

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    run_started = datetime.datetime.now().isoformat(timespec="seconds")

    # ---------------------------------------------------------------- 0-2 corpus, screening, filter
    U = parse(cfg)
    byid = {u["unit_id"]: u for u in U}
    S = screen(U, cfg)
    sby = {r["unit_id"]: r for r in S}
    cand = [r["unit_id"] for r in S if r["candidate"] and not r["excluded_by_filter"]]
    filt = [r["unit_id"] for r in S if r["candidate"] and r["excluded_by_filter"]]
    n_clin = len(S)
    log(f"[screen] clinical units {n_clin}; candidates {len(cand) + len(filt)}; filter-excluded {len(filt)}; to adjudicate {len(cand)}")
    write_csv("outputs/01_screening_all_clinical_units.csv",
              strip([dict(r, **{k: byid[r['unit_id']][k] for k in ('book', 'BB', 'CC', 'DD', 'type', 'name', 'text')})
                     for r in S]))

    # ---------------------------------------------------------------- 3 adjudication
    # Decision units: a candidate body passage with two or more source citations is judged source unit by
    # source unit ("<unit_id>#<k>", src/statements.py; researcher decision 2026-10-09), every other candidate whole.
    D = load_dictionary(cfg)
    P = load_patterns(cfg)
    dids = statements.decision_ids(cand, byid)
    ann = {did: annotate(statements.unit_of(did, byid), D, P) for did in dids}
    ann.update({uid: annotate(byid[uid], D, P) for uid in cand + filt})
    old = {o["unit_id"]: o for o in read_csv("data/old_analysis/old_decisions.csv") if o["unit_id"]}
    wb_path = path(cfg["adjudication"]["workbook"])
    dec, dec_from = adjudication.load_decisions(cfg)
    if dec_from is None:
        adjudication.build(cand, byid, sby, ann, old, filt, wb_path)
        log(f"[adjudication] workbook created: {wb_path}")
    elif dec_from == "workbook":
        adjudication.write_record(dec, path(cfg["adjudication"]["record"]))
    else:
        log(f"[adjudication] decisions read from the adjudication record ({cfg['adjudication']['record']})")
    missing = [uid for uid in cand if uid not in dec and not any(d in dec for d in statements.decision_ids([uid], byid))]
    if missing:
        p = out(f"재판정_추가대상_{datetime.date.today().isoformat()}.xlsx")
        adjudication.build(missing, byid, sby, ann, old, [], p)
        log(f"[adjudication] {len(missing)} candidate(s) not in the workbook -> {p}")
    final, decision_rows = [], []
    n_res = n_prov = n_acc = 0
    for did in dids:
        parent = statements.parent_of(did)
        d = dec.get(did)
        undivided = d is None and did != parent and parent in dec       # workbook row still the whole passage
        d = dec.get(parent, {}) if undivided else (d or {})
        v = d.get("최종판정", "")
        mark = d.get(adjudication.REVIEW, "") if adjudication.REVIEW in d else "확인"
        if v in ("포함", "제외") and mark in ("확인", "수정", adjudication.ACCEPTED) and not undivided:
            inc = v == "포함"
            if dec_from == "record":
                src = "adjudication record"
            elif mark == adjudication.ACCEPTED:   # researcher decision 2026-10-26: high-confidence proposals accepted
                src = "researcher accepted the AI proposal (high confidence, not reviewed row by row)"
                n_acc += 1
            else:
                src = "researcher"
            n_res += 1
        elif v in ("포함", "제외"):
            inc = v == "포함"
            src = "provisional: passage-level row, source units not yet judged" if undivided else \
                "provisional: AI proposal not yet reviewed"
            n_prov += 1
        else:
            o = old.get(parent, {})
            inc = o.get("old_status") == "kept162"
            src = "provisional: previous decision" if o else "provisional: new candidate, excluded until judged"
            n_prov += 1
        habit = d.get("배변양상", "")
        habit_code = {"설사": "D", "변비": "C", "혼합": "M", "미분류": "U"}.get(habit, "")
        decision_rows.append(dict(unit_id=did, passage=parent, included=inc, decision_source=src,
                                  bowel_habit=habit_code or ann[did]["auto_bowel_habit"],
                                  habit_source=(src if src in ("researcher", "adjudication record") else "AI proposal")
                                  if habit_code else "auto",
                                  patterns=ann[did]["auto_patterns"], **{k: d.get(k, "") for k in adjudication.DECISION_COLS}))
        if inc:
            final.append(did)
    n_div = sum(1 for uid in cand if statements.is_split(byid[uid]))
    accepted = f"; {n_acc} of them high-confidence AI proposals accepted without row-by-row review" if n_acc else ""
    by = "from the adjudication record" if dec_from == "record" else "by the researcher"
    status = f"FINAL (all decisions {by}{accepted})" if n_prov == 0 else \
        f"PROVISIONAL ({n_prov} of {len(dids)} decisions not yet entered or reviewed by the researcher{accepted})"
    # tiers (researcher decision 2026-10-10, Rome V since 2026-10-29): tier 1 = Rome V core, abdominal pain or
    # discomfort written together with at least two of relation to defecation, change in frequency, change in form
    # (R4 pain Y and frequency or form Y; no unit records a discomfort other than bloating, which Rome V keeps apart,
    # so the tiers are those of Rome IV as well); tier 2 = a change in bowel habit without such pain or discomfort
    yes = lambda r, k: r.get(k, "").strip().upper() == "Y"
    for r in decision_rows:
        r["tier"] = ("1" if yes(r, "R4_배변연관통증") and (yes(r, "R4_빈도변화") or yes(r, "R4_형태변화")) else "2") \
            if r["included"] else ""
    tier = {r["unit_id"]: int(r["tier"]) for r in decision_rows if r["tier"]}
    w2 = cfg["index"].get("tier2_weight", 0.5)

    def occ_of(ids, weight2=w2):
        """(unit, weight) for weighted herb frequency: tier 1 counts 1, tier 2 (and units without a tier) weight2."""
        return [(statements.unit_of(d, byid), 1.0 if tier.get(d) == 1 else weight2) for d in ids]

    FU = statements.reduced_units(final, byid)          # herb counts: passages, holding only their included text
    FS = [statements.unit_of(did, byid) for did in final]   # decision units (prescriptions are linked to these)
    n_t1 = sum(1 for d in final if tier[d] == 1)
    log(f"[adjudication] {len(dids)} decision units from {len(cand)} passages ({n_div} divided by source citation); "
        f"included {len(final)} units (tier 1 {n_t1}, tier 2 {len(final) - n_t1}) from {len(FU)} passages; {status}")
    write_csv("outputs/02_adjudication_status.csv", decision_rows)
    habit_by = {r["unit_id"]: r for r in decision_rows}
    sections_final = {u["BB"] for u in FU}

    # ---------------------------------------------------------------- 4 passage table (Supplementary)
    sup = []
    for did in final:
        u, a, d, parent = statements.unit_of(did, byid), ann[did], habit_by[did], statements.parent_of(did)
        sup.append(dict(unit_id=did, passage=parent, chapter=u["AA"], section=u["BB"], subsection=u["CC"], detail=u["DD"],
                        type=u["type"], prescription=u["name"], score=sby[parent]["score"], terms=sby[parent]["terms"],
                        link_terms=a["flag_link_terms"], pain_terms=a["flag_pain_terms"], stool_terms=a["flag_stool_terms"],
                        chronicity=a["flag_chronicity"], bowel_habit=d["bowel_habit"], habit_source=d["habit_source"],
                        patterns=a["auto_patterns"], inclusion_codes=d.get("포함근거", ""), tier=d["tier"],
                        decision_source=d["decision_source"], text=u["text"]))
    write_csv("outputs/03_final_passages.csv", strip(sup))
    elem = {k: sum(1 for r in sup if r[k]) for k in ("link_terms", "pain_terms", "stool_terms", "chronicity")}
    log("[passages] keyword-level Rome elements in final passages:", elem)

    # ---------------------------------------------------------------- 5 herbs and index
    lex = load_aliases(cfg)
    mk = Masker(formula_names(U, cfg))
    occ_base = occ_of(final)
    rows, info = herb_features(FU, U, lex, mk, D, cfg, occ_units=occ_base)
    w0 = cfg["index"]["weights"]
    base = score(copy.deepcopy(rows), w0)
    write_csv("outputs/04_herb_index.csv", base)
    log(f"[herbs] universe {len(base)} herbs (>= {cfg['herbs']['universe_min_passages']} final passages); "
        f"f_max {info['fmax']} (tier-2 mentions weighted {w2})")
    log("[herbs] top 10:", ", ".join(f"{r['herb']} {r['score']:.1f}" for r in base[:10]))
    write_csv("outputs/05_requisite_designations.csv",
              strip([dict(indication=d["indication"], herbs="|".join(d["herbs"]),
                          selected="yes" if d in info["selected"] else "", text=d["text"]) for d in info["designations"]]))
    write_csv("outputs/06_tonify_reduce_lists.csv",
              strip([dict(organ=k, **{kk: "|".join(v[kk]) for kk in ("溫用", "涼用", "補用", "瀉用")}, unit_id=v["unit_id"])
                     for k, v in info["tonify_lists"].items()], ("溫用", "涼用", "補用", "瀉用")))
    import collections as _c
    msrc_count = _c.Counter(r["meridian_source"] for r in base)
    log("[herbs] meridian source: " + ", ".join(f"{k} {v}" for k, v in sorted(msrc_count.items())))
    write_csv("outputs/07_meridian_source_by_herb.csv",
              [dict(herb=r["herb"], rank=r["rank"], meridians=r["meridians"], m_target=r["m_target"],
                    source=r["meridian_source"], citation=r["meridian_citation"],
                    donguibogam_meridians=r["donguibogam_meridians"]) for r in base])

    # ---------------------------------------------------------------- 6 sensitivity
    sbase, wres, wdist = sens.weight_sensitivity(rows, cfg)
    write_csv("outputs/10_weight_scenarios.csv", wres)
    write_csv("outputs/11_weight_random_draws.csv", [wdist])
    write_csv("outputs/12_ablation.csv", sens.ablation(rows, cfg))
    write_csv("outputs/13_worst_case_margins.csv", sens.worst_case_margins(base, cfg))
    rngs, corr, diag = sens.design_matrix(base)
    write_csv("outputs/14_design_matrix_ranges.csv", rngs)
    write_csv("outputs/15_design_matrix_spearman.csv", corr)
    write_csv("outputs/16_design_matrix_diagnostics.csv", [diag])
    write_csv("outputs/17_component_contributions.csv", sens.contributions(base))

    universe = info["universe"]
    alt = []
    rank_table = {"primary": {r["herb"]: r["rank"] for r in base}}

    def run_alt(label, ids=None, weight2=w2, **kw):
        """Alternative rule or corpus. ids: the included units it uses (default: the final units)."""
        ids = final if ids is None else ids
        r2, _ = herb_features(statements.reduced_units(ids, byid), U, lex, mk, D, cfg,
                              occ_units=occ_of(ids, weight2), **kw)
        s2 = score(r2, kw.get("weights", w0))
        alt.append(sens.compare(base, s2, label))
        rank_table[label] = {r["herb"]: r["rank"] for r in s2}
        return s2

    for rule in ("original8", "broad_gi", "all41", "none"):
        run_alt(f"requisite rule: {rule}", requisite_rule=rule, universe=universe)
    for rule in ("large_intestine_tonify_or_reduce", "large_intestine_plus_spleen_tonify", "none"):
        run_alt(f"tonify rule: {rule}", tonify_rule=rule, universe=universe)
    run_alt("meridians: Donguibogam first", meridian_priority=["Donguibogam", "KIOM monograph", "ChP 2020"], universe=universe)
    run_alt("meridians: Donguibogam only", meridian_priority=["Donguibogam"], universe=universe)
    dys = {u["unit_id"] for u in FU if "痢" in u["norm"]}
    run_alt(f"corpus: dysentery passages removed ({len(dys)} passages)",
            ids=[d for d in final if statements.parent_of(d) not in dys], universe=universe)
    hi = {u["unit_id"] for u in FU if sby[u["unit_id"]]["score"] >= 4}
    run_alt(f"corpus: passages with score >= 4 only ({len(hi)} of {len(FU)})",
            ids=[d for d in final if statements.parent_of(d) in hi], universe=universe)
    # tiers (2026-10-10): no differentiation (tier 2 counts 1), and tier 1 only (the Rome V core definition)
    run_alt("tiers: tier-2 mentions weighted 1 (no differentiation)", weight2=1.0, universe=universe)
    t1_ids = [d for d in final if tier[d] == 1]
    run_alt(f"tiers: tier 1 only, Rome V core ({len(t1_ids)} units)", ids=t1_ids, universe=universe)
    # dysentery rule A (2026-10-10): add back the chronic or functional-looking dysentery units whose own text names
    # no blood or pus (weighted as tier 2)
    fin = set(final)
    chronic_dys = [d for d in dids if d not in fin and statements.unit_of(d, byid)["BB"] == "大便"
                   and statements.unit_of(d, byid)["DD"] in ("氣痢", "寒痢", "虛痢", "休息痢", "久痢")
                   and not re.search("[血膿赤]", statements.unit_of(d, byid)["norm"])]
    run_alt(f"corpus: + chronic dysentery units without blood or pus ({len(chronic_dys)} units)",
            ids=[d for d in dids if d in fin or d in chronic_dys], universe=universe)
    # independent rating (2026-10-27): the units both raters judged relevant that the procedure did not include, added
    # to the corpus as they are and weighted by the inverse sampling probability of their passage, so that a sampled
    # unit stands for the units of its stratum. Added units have no tier and count at the tier-2 weight. Uses the
    # rating results of run_d2.py analyze (d2/d2_per_unit.csv); skipped before the rating has been analysed.
    per_unit = os.path.join(cfg["d2"]["folder"], "d2_per_unit.csv")
    if os.path.exists(path(per_unit)):
        missed = [r for r in read_csv(per_unit) if r["reference"] == "포함" and r["author"] != "포함"]
        mids = [r["unit_id"] for r in missed]
        label = f"corpus: + units both raters judged relevant but not included ({len(mids)} units)"
        run_alt(label, ids=list(final) + mids, universe=universe)
        inv = {r["unit_id"]: 1.0 / float(r["prob"]) for r in missed}
        occ = occ_of(final) + [(statements.unit_of(d, byid), w2 * inv[d]) for d in mids]
        r2, _ = herb_features(statements.reduced_units(list(final) + mids, byid), U, lex, mk, D, cfg, occ_units=occ,
                              universe=universe)
        s2 = score(r2, w0)
        label_w = label.replace("not included", "not included, weighted by inverse sampling probability")
        alt.append(sens.compare(base, s2, label_w))
        rank_table[label_w] = {r["herb"]: r["rank"] for r in s2}
    for kmin in (1, 3):
        r2, _ = herb_features(FU, U, lex, mk, D, cfg, occ_units=occ_base,
                              universe=sorted(h for h, n in info["passage_counts"].items() if n >= kmin and lex["kind"].get(h) == "herb"))
        s2 = score(r2, w0)
        alt.append(sens.compare(base, s2, f"herb universe: >= {kmin} final passage(s) ({len(s2)} herbs)"))
    old75 = [norm(r["herb"]) for r in read_csv("data/old_analysis/herb_intrinsic_scores_original.csv")]
    old75c = sorted({lex["alias2canon"].get(h, h) for h in old75})
    r2, _ = herb_features(FU, U, lex, mk, D, cfg, occ_units=occ_base, universe=[h for h in old75c if h in lex["kind"]])
    s2 = score(r2, w0)
    alt.append(sens.compare(base, s2, f"herb universe: original 75 herbs ({len(s2)} matched)"))
    # frequency as passage count, TF-IDF, M removed
    r3 = copy.deepcopy(rows)
    pmax = max(r["passages"] for r in r3)
    for r in r3:
        r["zF"] = np.log1p(r["passages"]) / np.log1p(pmax)
    alt.append(sens.compare(base, score(r3, w0), "frequency = number of passages (not occurrences)"))
    corpus_doc = {}
    for u in U:
        if u["chapter_class"] == "clinical":
            for h in set(unit_mentions(u, lex, mk)):
                corpus_doc[h] = corpus_doc.get(h, 0) + 1
    tf = sens.tfidf_variant(rows, corpus_doc, n_clin)
    stf = score(tf, w0)
    alt.append(sens.compare(base, stf, "TF-IDF specificity (F = ln(1+f)·ln(N/df), rescaled)"))
    rank_table["TF-IDF"] = {r["herb"]: r["rank"] for r in stf}
    write_csv("outputs/18_alternative_rules_and_corpora.csv", alt)
    write_csv("outputs/19_enrichment.csv", sens.enrichment(base, info["passage_counts"], corpus_doc, len(FU), n_clin))
    ks, kd = sens.kiom_comparison(base, load_meridian_sources(cfg), cfg["index"]["meridian_targets"], cfg)
    write_csv("outputs/20_kiom_comparison_summary.csv", [ks])
    write_csv("outputs/21_kiom_vs_donguibogam_meridians.csv", kd)
    # comparison with the submitted ranking
    oldrank = {norm(r["herb"]): float(r["DGBG"]) for r in read_csv("data/old_analysis/table4_herb_ranking_original.csv")}
    common = [r for r in base if r["herb"] in oldrank]
    write_csv("outputs/22_vs_submitted_ranking.csv",
              [dict(herb=r["herb"], new_rank=r["rank"], new_score=round(r["score"], 1),
                    submitted_score=oldrank[r["herb"]]) for r in base if r["herb"] in oldrank] +
              [dict(herb=h, new_rank="", new_score="not in universe", submitted_score=v) for h, v in oldrank.items()
               if h not in {r["herb"] for r in base}])
    if len(common) > 2:
        log(f"[compare] submitted vs new, common herbs {len(common)}: Spearman "
            f"{stats.spearman([oldrank[r['herb']] for r in common], [r['score'] for r in common]):.3f}")

    # ---------------------------------------------------------------- 7 prescriptions
    hs = {r["herb"]: r["score"] for r in base}
    # bowel habit: as judged for the unit that records or recommends the formula; patterns: read from the
    # included text of its passage (a treatment sentence rarely names the pattern it treats)
    pat_of = {u["unit_id"]: annotate(u, D, P)["auto_patterns"] for u in FU}
    pa = {did: dict(bowel_habit=habit_by[did]["bowel_habit"], patterns=pat_of[statements.parent_of(did)],
                    habit_source=habit_by[did]["habit_source"], tier=tier[did]) for did in final}
    fl = formula_names(U, cfg)
    composer = Composer(U, lex, mk, fl, [k for k in tangaek_entries(U) if ">" not in k])
    pres = prescription_table(FS, U, composer, hs, pa, fl)
    write_csv("outputs/30_prescriptions.csv", pres)
    write_csv("outputs/31_prescriptions_by_bowel_habit.csv", stratified(pres, "bowel_habit", k=10))
    write_csv("outputs/32_prescriptions_by_pattern.csv", stratified(pres, "patterns", k=5))
    formulas = [p for p in pres if p["kind"] == "formula"]
    if formulas:
        a = [p["score_zero"] for p in formulas]
        b = [p["score_scored"] for p in formulas]
        dd = [(p["score_zero"], p["score_dose"]) for p in formulas if p["score_dose"] != ""]
        log(f"[prescriptions] {len(formulas)} formulas ({sum(p['source'].startswith('recorded') for p in formulas)} recorded in, "
            f"{sum(p['source'].startswith('recommended') for p in formulas)} recommended in IBS passages; "
            f"+{len(pres) - len(formulas)} single-herb remedies); "
            f"Spearman zero vs scored-only {stats.spearman(a, b):.3f}; "
            f"dose-weighted available for {len(dd)}" + (f", Spearman {stats.spearman([x for x, _ in dd], [y for _, y in dd]):.3f}" if len(dd) > 2 else ""))

    # ---------------------------------------------------------------- 8 acupoints
    acu = acupoints.extract(U, sections_final, D)
    nums = {}
    for r in acu:       # statements numbered within their unit, so that rows stay distinct without the text
        seen = nums.setdefault(r["unit_id"], {})
        r["statement_no"] = seen.setdefault(r["statement"], len(seen) + 1)
    # every statement judged by the adjudication criteria of the units (researcher decision 2026-10-28)
    acupoints.apply_decisions(acu, acupoints.load_decisions(), dec)
    write_csv("outputs/40_acupoint_statements.csv", strip(acu, ("statement", "indication")))
    acs = acupoints.summarize(acu, read_csv("data/cpg_acupoints.csv"))
    write_csv("outputs/41_acupoints_summary.csv", strip(acs, ("indications",)))
    inc = {(r["unit_id"], r["statement"]) for r in acu if r["decision"] == "included"}
    log(f"[acupoints] {len(acs)} points from {len(inc)} included statements of "
        f"{len({(r['unit_id'], r['statement']) for r in acu})} extracted "
        f"({sum(1 for r in acu if not r['reviewed'] and r['decision'])} point-mentions from statement decisions "
        f"awaiting the researcher's review)")

    # ---------------------------------------------------------------- 9 figures
    counts = dict(units=n_clin, threshold=cfg["screening"]["threshold"], candidates=len(cand) + len(filt),
                  filtered=len(filt), adjudicated=len(cand), divided=n_div, adjudicated_units=len(dids),
                  included=len(final), included_passages=len(FU), tier1=n_t1, tier2=len(final) - n_t1,
                  tier1_passages=len({statements.parent_of(d) for d in t1_ids}), tier2_weight=w2,
                  note="" if n_prov == 0 else f"Provisional: {n_prov} adjudication decisions not yet entered by the researcher")
    figures.flow(counts, out("fig1_flow.png"))
    labels = figures.latin_labels()
    figures.contributions(base, out("fig2_component_contributions.png"), labels=labels)
    top = [r["herb"] for r in sorted(base, key=lambda r: (r["rank"], r["herb"])) if r["rank"] <= 20]  # ties included
    figures.rank_stability(rank_table, top, out("fig3_rank_stability.png"), labels=labels)

    # ---------------------------------------------------------------- summary workbook + manifest
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for fn in sorted(os.listdir(OUT)):
        if fn.endswith(".csv"):
            ws = wb.create_sheet(fn[:31].replace(".csv", ""))
            with open(out(fn), encoding="utf-8-sig") as f:
                for row in csv.reader(f):
                    ws.append(row)
    wb.save(out("결과요약_R1.xlsx"))
    inputs = {}
    for rel in ["config.json"] + [os.path.join("data", f) for f in sorted(os.listdir(path("data"))) if f.endswith(".csv")] + \
               [os.path.join("data", "old_analysis", f) for f in sorted(os.listdir(path("data", "old_analysis")))]:
        inputs[rel] = md5(path(rel))
    if dec_from == "workbook":
        inputs[cfg["adjudication"]["workbook"]] = md5(wb_path)
    elif dec_from == "record":
        inputs[cfg["adjudication"]["record"]] = md5(path(cfg["adjudication"]["record"]))
    code = {os.path.join("src", f): md5(path("src", f)) for f in sorted(os.listdir(path("src"))) if f.endswith(".py")}
    code["run_all.py"] = md5(path("run_all.py"))
    manifest = dict(version=cfg["version"], run_started=run_started, status=status, python=sys.version.split()[0],
                    platform=platform.platform(), numpy=np.__version__, openpyxl=openpyxl.__version__,
                    source_texts=source_manifest(cfg), source_texts_sha256=source_manifest(cfg, sha256),
                    inputs=inputs, code=code, seeds=cfg["sensitivity"],
                    counts=counts)
    json.dump(manifest, open(out("manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(out("run_log.txt"), "w", encoding="utf-8").write("\n".join(LOG) + "\n")
    log("[done]", status)


if __name__ == "__main__":
    main()
