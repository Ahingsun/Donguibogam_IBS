"""D2 independent expert rating.

    python run_d2.py build     draw the stratified sample and write blinded rater workbooks to d2/
    python run_d2.py analyze   read the filled rater workbooks and compute agreement, precision, recall

build refuses to overwrite existing materials (they may already be with the raters); use --force
only before anything has been sent out. analyze writes the key and the answers without the passages to
d2/rating_key.csv and d2/ratings.csv, and reads those when the workbooks are absent. The first author's labels for
the units on which the raters disagreed (d2/불일치_저자판정.xlsx, column author_label of ratings.csv) give the
secondary estimates in d2_summary.json["with_author_labels"]; the primary estimates use the units the raters agreed on.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from openpyxl import Workbook, load_workbook  # noqa: E402

import d2  # noqa: E402
import statements  # noqa: E402
import re  # noqa: E402

from adjudication import ACCEPTED, REVIEW, load_decisions  # noqa: E402
from common import load_config, path, read_csv  # noqa: E402
from corpus import parse  # noqa: E402
from screen import screen  # noqa: E402


def current_decisions(cfg, cand, units_by_id):
    """Author decision for every decision id of the candidates (source units of divided passages, else the passage).
    A decision counts as final only when the researcher entered or reviewed it; otherwise it is provisional: an
    unreviewed AI proposal, the passage row of a workbook not yet divided, or the previous decision."""
    dec, _ = load_decisions(cfg)
    old = {o["unit_id"]: o for o in read_csv("data/old_analysis/old_decisions.csv") if o["unit_id"]}
    out, n_prov = {}, 0
    for did in statements.decision_ids(cand, units_by_id):
        d = dec.get(did) or {}
        v = d.get("최종판정", "")
        if v in ("포함", "제외"):
            out[did] = v == "포함"
            n_prov += REVIEW in d and d.get(REVIEW, "") not in ("확인", "수정", ACCEPTED)
            continue
        p = (dec.get(statements.parent_of(did)) or {}).get("최종판정", "")
        out[did] = p == "포함" if p in ("포함", "제외") else old.get(statements.parent_of(did), {}).get("old_status") == "kept162"
        n_prov += 1
    return out, n_prov


BLOOD = re.compile(r"血|膿|赤白|赤痢|紫黑")


def post_rating_rule_units(cfg, units_by_id):
    """Units the author excluded only under a rule adopted after the rating files were sent on 2026-10-10:
    explicit absence of pain (E-8, 2026-10-25), alarm features (E-9, 2026-10-10) and dysentery as a category
    (decision A, 2026-10-10; an E-1 unit that names no blood or pus, since bloody stool was already in the raters'
    instructions)."""
    out = set()
    for uid, d in load_decisions(cfg)[0].items():
        if d.get("최종판정") != "제외":
            continue
        codes = {c.strip() for c in d.get("제외코드", "").split(",")}
        if codes & {"E-8", "E-9"} or ("E-1" in codes and not BLOOD.search(statements.unit_of(uid, units_by_id)["text"])):
            out.add(uid)
    return out


def passage_level(dec):
    """A passage counts as included when any of its units is included (used only to rebuild the strata)."""
    out = {}
    for did, inc in dec.items():
        out[statements.parent_of(did)] = out.get(statements.parent_of(did), False) or inc
    return out


def build(force=False):
    cfg = load_config()
    folder = path(cfg["d2"]["folder"])
    keyp = os.path.join(folder, "평정키_연구자보관.xlsx")
    if os.path.exists(keyp) and not force:
        print(f"materials already exist in {folder}; not overwritten (use --force only if nothing was sent out)")
        return
    U = parse(cfg)
    byid = {u["unit_id"]: u for u in U}
    S = screen(U, cfg)
    cand = [r["unit_id"] for r in S if r["candidate"] and not r["excluded_by_filter"]]
    dec, n_prov = current_decisions(cfg, cand, byid)
    dec = passage_level(dec)
    final_sections = {byid[u]["BB"] for u, inc in dec.items() if inc}
    frame = d2.build_frame(S, byid, dec, final_sections)
    sizes = cfg["d2"]["designs"][cfg["d2"]["design"]]
    sample, prob, cal = d2.draw(frame, sizes, cfg["d2"]["seed"], cfg["d2"]["n_calibration"])
    paths, key = d2.build_materials(sample, cal, byid, folder, cfg["d2"]["n_raters"])
    kp = d2.save_key(key, sample, prob, cal, folder)
    chars = sum(len(byid[u]["text"]) for u, _ in sample) + sum(len(byid[u]["text"]) for u in cal)
    info = dict(design=cfg["d2"]["design"], seed=cfg["d2"]["seed"], provisional_decisions=n_prov,
                frame={s: len(v) for s, v in frame.items()},
                sampled={s: sum(1 for _, x in sample if x == s) for s in d2.STRATA},
                inclusion_probability=prob, n_rating=len(sample), n_calibration=len(cal), characters=chars)
    json.dump(info, open(os.path.join(folder, "design.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    print("written:", *paths, kp, sep="\n  ")


def analyze():
    cfg = load_config()
    folder = path(cfg["d2"]["folder"])
    key = d2.read_key(folder)
    U = parse(cfg)
    byid = {u["unit_id"]: u for u in U}
    items = d2.rating_items(key, byid)
    expected = {i for i, _, _, s, _ in items if s != "calibration"}
    fa, fb = cfg["d2"]["rater_files"]          # second version, divided by source citation (2026-10-09)
    workbooks = os.path.exists(os.path.join(folder, fa)) and os.path.exists(os.path.join(folder, fb))
    if workbooks:
        ra = d2.read_rater(os.path.join(folder, fa))
        rb = d2.read_rater(os.path.join(folder, fb))
        ap = os.path.join(folder, d2.AUTHOR_LABELS)
        rc = d2.read_rater(ap) if os.path.exists(ap) else None
        d2.write_key_csv(key, folder)
        d2.write_ratings(items, [ra, rb], folder, author=rc)
    else:
        ratings = d2.read_ratings(folder)
        ra, rb, rc = ratings["rater_1"], ratings["rater_2"], ratings.get(d2.AUTHOR_COL)
    for fname, r in ((fa, ra), (fb, rb)):
        if set(r) != expected:
            raise SystemExit(f"{fname}: its rows are not the rows of the current design "
                             f"({len(set(r) - expected)} unexpected, {len(expected - set(r))} missing). "
                             "Was a file of the first version (sent 2026-10-08) returned?")
    adj_p = os.path.join(folder, "불일치_조정.xlsx")
    adj = {}
    if os.path.exists(adj_p):
        for r in list(load_workbook(adj_p, read_only=True)["조정"].iter_rows(values_only=True))[1:]:
            if r and r[0] and r[-1] in ("포함", "제외"):
                adj[r[0]] = r[-1]
    by_rid = {rid: uid for rid, uid, *_ in items}
    labels = {by_rid[rid]: v for rid, v in ((rid, d2.judgement(row)) for rid, row in (rc or {}).items())
              if rid in by_rid and v in ("포함", "제외")}
    S = screen(U, cfg)
    cand = [r["unit_id"] for r in S if r["candidate"] and not r["excluded_by_filter"]]
    dec, n_prov = current_decisions(cfg, cand, byid)
    included = {u for u, v in dec.items() if v}
    summ, per = d2.analyze(items, ra, rb, adj, included, cfg["d2"]["seed"], cfg["d2"]["bootstrap"])
    summ["author_decisions_provisional"] = n_prov
    summ["blank_ratings"] = {f: sorted(i for i in expected if d2.judgement(r.get(i)) not in ("포함", "제외"))
                             for f, r in ((fa, ra), (fb, rb))}
    summ.update(d2.analyze_more(per, post_rating_rule_units(cfg, byid), cfg["d2"]["seed"], cfg["d2"]["bootstrap"]))
    if labels:
        summ["with_author_labels"] = d2.with_author_labels(per, labels, cfg["d2"]["seed"], cfg["d2"]["bootstrap"])
    # what the consensus misses are, for the text: the author's exclusion reason at adjudication, and the kind of
    # entry below the screening threshold (formula or single-herb entry vs body text)
    codes = {u: d.get("제외코드", "") for u, d in load_decisions(cfg)[0].items()}
    order = [("E-1", "dysentery or bloody stool"), ("E-3", "acute disease"), ("E-9", "alarm feature"),
             ("E-8", "pain explicitly absent"), ("E-4", "incidental mention"), ("E-5", "theory or prognosis"),
             ("E-7", "systemic disease"), ("E-6", "no change in bowel habit"), ("E-2", "child")]
    reason = lambda c: next((name for k, name in order if k in c), c or "none")
    miss = [x for x in per if x["reference"] == "포함" and x["author"] == "제외"]
    tally = lambda xs: dict(sorted({k: sum(1 for y in xs if y == k) for k in set(xs)}.items(), key=lambda kv: (-kv[1], kv[0])))
    summ["adjudication_miss_reasons"] = tally([reason(codes.get(x["unit_id"], "")) for x in miss
                                               if x["stratum"] in ("A", "B")])
    kind = lambda u: "single-herb entry" if byid[u]["CC"] == "單方" else \
        "formula entry" if byid[u]["type"] != "body" else "body text"
    summ["screening_miss_kinds"] = tally([kind(statements.parent_of(x["unit_id"])) for x in miss
                                          if x["stratum"] in ("D2", "D1", "E")])
    dis = [x for x in per if x["rater_a"] != x["rater_b"] and not x["reference"]]
    if dis and workbooks and not os.path.exists(adj_p):
        wb = Workbook()
        ws = wb.active
        ws.title = "조정"
        ws.append(["unit_id", "검토ID", "검토위원1", "검토위원2", "조정 판정(포함/제외)"])
        for x in dis:
            ws.append([x["unit_id"], x["rating_id"], x["rater_a"], x["rater_b"], ""])
        wb.save(adj_p)
        print(f"{len(dis)} disagreements written to {adj_p} for adjudication")
    with open(os.path.join(folder, "d2_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    if labels:
        for x in per:
            x[d2.AUTHOR_COL] = "" if x["reference"] else labels.get(x["unit_id"], "")
    with open(os.path.join(folder, "d2_per_unit.csv"), "w", encoding="utf-8-sig", newline="") as f:
        if per:
            w = csv.DictWriter(f, fieldnames=list(per[0].keys()))
            w.writeheader()
            w.writerows(per)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build(force="--force" in sys.argv)
    elif cmd == "analyze":
        analyze()
    else:
        print(__doc__)
