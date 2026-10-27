"""Step 7. Acupoints (definition D8-b).

Scope
  (a) statements in the acupuncture-moxibustion subsection (CC contains 鍼灸) of every section (BB)
      that holds at least one final passage, and
  (b) acupoint entries of the Acupuncture chapter (DK) whose indication (主…) is a bowel symptom.
In (a) the text is split at source citations 《…》 and then into sentences; a sentence that names
points takes as its indication the preceding point-free sentences of the same citation group plus
its own text before the first 取/灸/刺/鍼.
A statement is kept when its indication names a bowel symptom: a screening-dictionary symptom term,
or 泄 瀉 痢 秘 閉 大便 腹痛 脹 腸鳴. Statements that mention blood in stool, postpartum or acute febrile
illness are kept but flagged, and they are not counted in the summary table.
Acupoints are reported qualitatively; no frequency ranking is attempted.
"""
import re

from common import norm, read_csv

ACTION_RX = re.compile(r"取|灸|刺|鍼")
BOWEL_RX = re.compile(r"泄|痢|秘|閉|大便|大小便不通|腹痛|脹|腸鳴")   # 瀉 left out: in acupuncture texts it usually means the draining technique
FLAG_RX = {"bloody_stool": re.compile(r"膿血|便血|下血"), "postpartum": re.compile(r"産後|胎"),
           "acute_febrile": re.compile(r"傷寒|暑|瘧|疫|熱病"), "systemic": re.compile(r"鼓脹|蠱脹|水蠱|水腫|浮腫")}
SYMPTOM_DOMAINS = ("C1", "C2/C3", "supportive-distension")      # appetite terms are not bowel symptoms here


def load_points():
    rows = read_csv("data/acupoint_names.csv")
    alias = {}
    for r in rows:
        for a in r["aliases"].split("|"):
            alias[norm(a)] = r
    rx = re.compile("|".join(map(re.escape, sorted(alias, key=len, reverse=True))))
    return alias, rx


def citation_groups(text):
    groups, cur = [], ""
    for seg in re.split(r"(《[^》]*》)", text):
        if seg.startswith("《"):
            groups.append((cur.strip(), seg))
            cur = ""
        else:
            cur += seg
    if cur.strip():
        groups.append((cur.strip(), ""))
    return groups


def symptom_ok(ind, sym_terms):
    return any(t in ind for t in sym_terms) or bool(BOWEL_RX.search(ind))


def extract(all_units, final_sections, dictionary):
    alias, rx = load_points()
    sym = [d["norm"] for d in dictionary if d["domain"] in SYMPTOM_DOMAINS]
    rows = []

    def add(p, ind, stmt, src, u, scope, context=""):
        flags = [k for k, r in FLAG_RX.items() if r.search(stmt + " " + context)]
        rows.append(dict(point=p["name"], who_code=p["who_code"], kind=p["kind"], indication=ind.strip(" ,."),
                         statement=stmt.strip(), citation=src, section=f"{u['BB']}/{u['CC']}",
                         unit_id=u["unit_id"], scope=scope, flags="|".join(flags)))

    for u in all_units:
        if u["chapter_class"] == "clinical" and "鍼灸" in u["CC"] and u["BB"] in final_sections:
            scope = "IBS-related section, acupuncture-moxibustion subsection"
            for body, src in citation_groups(norm(u["text"])):
                pending = ""
                for sent in [s for s in re.split(r"(?<=[.。])\s*", body) if s.strip()]:
                    pts = [alias[m.group(0)] for m in rx.finditer(sent)]
                    if not pts:
                        pending += sent + " "
                        continue
                    a = ACTION_RX.search(sent)
                    first_pt = rx.search(sent)
                    cut = min(x.start() for x in (a, first_pt) if x is not None)
                    ind = pending + sent[:cut]
                    context = pending
                    pending = ""
                    if symptom_ok(ind, sym):
                        seen = set()
                        for p in pts:
                            if p["name"] not in seen:
                                seen.add(p["name"])
                                add(p, ind, sent, src, u, scope, context)
        elif u["type"] == "acup":
            scope = "Acupuncture chapter, acupoint entry"
            m = re.match(r"^(\S+?)[一二三四八十]穴", norm(re.sub(r"\s+", "", u["name"])))
            if not m or norm(m.group(1)) not in alias:
                continue
            t = norm(u["text"])
            mm = re.search(r"主([^.。]+)", t)
            if mm and symptom_ok(mm.group(1), sym):
                add(alias[norm(m.group(1))], mm.group(1), t, "", u, scope)
    return rows


# indication type of a statement, for description only (a statement can be both)
DIARRHEA_RX = re.compile(r"泄|瀉|痢|溏")
CONSTIPATION_RX = re.compile(r"秘|閉|不通|大便難")


def summarize(rows, cpg_rows):
    cpg = {}
    for r in cpg_rows:
        for c in r["who_codes"].split("|"):
            cpg.setdefault(c, []).append(f"{r['recommendation']} {r['intervention']} ({r['grade']}, p.{r['pdf_page']})")
    by = {}
    for r in rows:
        if r["flags"]:
            continue
        d = by.setdefault(r["point"], dict(point=r["point"], who_code=r["who_code"], kind=r["kind"],
                                           indications=[], sources=[], n=0, nd=0, nc=0))
        d["n"] += 1
        d["nd"] += bool(DIARRHEA_RX.search(r["indication"]))
        d["nc"] += bool(CONSTIPATION_RX.search(r["indication"]))
        if r["indication"] not in d["indications"]:
            d["indications"].append(r["indication"])
        s = f"{r['section']} {r['citation']}".strip()
        if s not in d["sources"]:
            d["sources"].append(s)
    out = [dict(point=d["point"], who_code=d["who_code"], kind=d["kind"], n_statements=d["n"],
                n_diarrhea_dysentery=d["nd"], n_constipation=d["nc"],
                indications="; ".join(d["indications"]), sources="; ".join(d["sources"]),
                in_cpg="; ".join(cpg.get(d["who_code"], [])) if d["who_code"] else "")
           for d in by.values()]
    out.sort(key=lambda r: (-r["n_statements"], r["who_code"] or "ZZ", r["point"]))
    return out
