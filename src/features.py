"""Step 5. Herb universe and the six index components.

S_i = sum_m w_m z_im, w = (F 25, E 25, M 15, R 15, P 10, T 10), z_im in [0, 1].

F frequency   z = ln(1+f_i) / ln(1+f_max); f_i = occurrences of herb i (any alias) in the final passages.
E efficacy    z = min(k_i, 3) / 3; k_i = number of the 8 efficacy axes with a trigger term in the
              herb's Tangaek entry (data/efficacy_axes.csv).
M meridian    z = min(m_i, 3) / 3; m_i = number of target organs (脾 胃 大腸 小腸 肝 腎) among the herb's
              meridians, taken from the first available source in config priority.
R requisite   z = 1 if the herb is named in a selected 須用 designation of 湯液序例 諸經引導.
P patterns    z = min(p_i, 4) / 4; p_i = number of the 7 IBS patterns linked to the herb's axes
              (data/axis_pattern_map.csv).
T tonify      z = 1 if the herb is listed under 大腸 補用 in 湯液序例 五臟補瀉.
Ties share the minimum rank. A herb without meridian information in any declared source gets
m = 0 and is flagged; no value is imputed.
"""
import math
import re

from common import load_config, norm, read_csv

ORGANS = ["心包", "小腸", "大腸", "膀胱", "三焦", "肝", "心", "脾", "肺", "腎", "膽", "胃"]
CHANNEL2ORGAN = {("手", "太陰"): "肺", ("手", "陽明"): "大腸", ("足", "陽明"): "胃", ("足", "太陰"): "脾",
                 ("手", "少陰"): "心", ("手", "太陽"): "小腸", ("足", "太陽"): "膀胱", ("足", "少陰"): "腎",
                 ("手", "厥陰"): "心包", ("手", "少陽"): "三焦", ("足", "少陽"): "膽", ("足", "厥陰"): "肝"}
CH = "太陰|少陰|厥陰|太陽|陽明|少陽"
ENTRY_RX = re.compile(r"入((?:(?:手足|手|足)?(?:" + CH + r")(?:ㆍ|·)?)+)(?:[二三四五六]?經)?")
PART_NAMES = set("葉根子殼花肉皮核實莖油粉膽血頭骨髓脂膏毛尾蹄乳汁心肝肺腎腸胃齒角筋眼脣舌卵糞屎尿涎鬚爪甲")


# ------------------------------------------------------------------ Tangaek entries
def tangaek_entries(units):
    """Map 'name' and 'parent>part' (normalized) to the entry unit. Generic part names
    (葉 根 子 殼 ...) are attached to the preceding main entry."""
    out, parent = {}, None
    for u in units:
        if u["type"] != "herb":
            continue
        m = re.match(r"^(?:唐\s*)?([㐀-鿿\U00020000-\U0002ffff]+)", u["name"])
        nm = norm(m.group(1)) if m else ""
        if not nm:
            continue
        if (len(nm) == 1 and nm in PART_NAMES) or (len(nm) == 2 and all(ch in PART_NAMES for ch in nm)):
            if parent:
                out.setdefault(f"{parent}>{nm}", u)
        else:
            parent = nm
            out.setdefault(nm, u)
    return out


def entry_text(canon, lex, entries):
    key = norm(lex["meta"][canon]["tangaek_entry"] or "")
    if not key:
        return None, ""
    u = entries.get(key)
    return (u["unit_id"], norm(u["text"])) if u else (None, "")


# ------------------------------------------------------------------ efficacy and patterns
def load_axes(cfg):
    axes = []
    for r in read_csv(cfg["index"]["efficacy_axes"]):
        axes.append(dict(axis=int(r["axis"]), code=r["code"], triggers=[norm(t) for t in r["triggers"].split("|")]))
    amap = {int(r["axis"]): r["patterns"].split("|") for r in read_csv(cfg["index"]["axis_pattern_map"])}
    return axes, amap


NEG_CONTEXT = re.compile(r"(令人|使人|致人)$")
FALSE_CONTEXTS = {"利水": ("利水穀",)}      # 利水穀道 = passage of water and grain, not diuresis


def code_axes(text, axes):
    hits = {}
    for a in axes:
        found = []
        for t in a["triggers"]:
            for m in re.finditer(re.escape(t), text):
                if NEG_CONTEXT.search(text[max(0, m.start() - 2):m.start()]):
                    continue
                if any(text.startswith(fc, m.start()) for fc in FALSE_CONTEXTS.get(t, ())):
                    continue
                found.append(t)
                break
        if found:
            hits[a["axis"]] = found
    return hits


# ------------------------------------------------------------------ meridians
def parse_organs(s):
    s = norm(s)
    out, i = [], 0
    while i < len(s):
        for o in ORGANS:
            if s.startswith(o, i):
                out.append(o)
                i += len(o)
                break
        else:
            i += 1
    return out


def donguibogam_channels(text):
    """Organs named in 入…經 statements of a Tangaek entry (e.g. 入手太陽ㆍ少陰…四經: small intestine, heart, ...)."""
    organs = []
    for m in ENTRY_RX.finditer(text):
        seq = m.group(1)
        prefix = None
        for pm in re.finditer(r"(手足|手|足)?(" + CH + ")", seq):
            if pm.group(1):
                prefix = pm.group(1)
            if prefix is None:
                continue
            for side in (("手", "足") if prefix == "手足" else (prefix,)):
                organs.append(CHANNEL2ORGAN[(side, pm.group(2))])
    return sorted(set(organs), key=ORGANS.index)


def load_meridian_sources(cfg):
    src = {}
    for r in read_csv(cfg["index"]["meridian_sources"]):
        src.setdefault(norm(r["herb"]), []).append(r)
    return src


# ------------------------------------------------------------------ 湯液序例 lists
def requisite_designations(units):
    u = next(x for x in units if x["book"] == "탕액편_권01" and x["CC"] == "諸經引導")
    t = norm(u["text"])
    out = []
    for m in re.finditer(r"([^.。]+?), 須用([^.。]+)", t):
        ind = re.sub(r"《[^》]*》", "", m.group(1)).strip()
        herbs_raw = m.group(2)
        herbs = []
        for h in re.split(r"[,ㆍ]", herbs_raw):
            h = h.strip()
            if not h or "加" in h:
                continue
            h = re.sub(r"^(酒洗|酒製)", "", h)
            h = re.sub(r"(幷酒製|幷)$", "", h)
            herbs.append(h)
        out.append(dict(indication=ind, herbs=herbs, text=m.group(0).strip(), unit_id=u["unit_id"]))
    return out


def tonify_reduce_lists(units):
    out = {}
    for u in units:
        if u["book"] == "탕액편_권01" and u["CC"] == "五臟補瀉" and u["DD"]:
            t = norm(u["text"])
            d = {}
            for kind in ("溫用", "涼用", "補用", "瀉用"):
                m = re.search(kind + r"([^.]+)\.", t)
                d[kind] = [h.strip() for h in m.group(1).split(",") if h.strip()] if m else []
            out[u["DD"]] = dict(d, unit_id=u["unit_id"])
    return out


PREFACE_GI_RX = re.compile(r"腹|胃|脾|食|瀉|泄|痞|滯氣|調氣|氣刺")
ORIGINAL8 = ["腹痛", "小腹痛", "胃脘痛", "腹脹", "水瀉", "宿食不消", "破滯氣", "調氣"]


def select_designations(desigs, rule, dictionary):
    sym = [d["norm"] for d in dictionary if d["symptom_domain"] == "yes"]
    sel = []
    for d in desigs:
        ind = d["indication"]
        if rule == "dictionary_symptom_terms":
            probe = ind.replace("瀉", "泄")
            ok = any(t in ind or t in probe for t in sym)
        elif rule == "original8":
            ok = ind in ORIGINAL8
        elif rule == "broad_gi":
            ok = bool(PREFACE_GI_RX.search(ind))
        elif rule == "all41":
            ok = True
        elif rule == "none":
            ok = False
        else:
            raise ValueError(rule)
        if ok:
            sel.append(d)
    return sel


# ------------------------------------------------------------------ assemble
def herb_features(final_units, all_units, lex, masker, dictionary, cfg=None, requisite_rule=None,
                  tonify_rule=None, universe=None, meridian_priority=None, dysentery_free=None, occ_units=None):
    """Return (rows, info). rows: one dict per herb in the universe with raw values and z-scores.
    final_units are passages (holding only their included text) and give the passage counts. occ_units, when given,
    is a list of (unit, weight) whose weighted mentions give the frequency f (tier weighting, 2026-10-10);
    otherwise every mention in final_units counts 1."""
    from lexicon import unit_mentions
    cfg = cfg or load_config()
    requisite_rule = requisite_rule or cfg["index"]["requisite_rule"]
    tonify_rule = tonify_rule or cfg["index"]["tonify_rule"]
    meridian_priority = meridian_priority or ["textbook", "KIOM monograph", "textbook (original analysis record)", "Donguibogam"]
    occ, docf = {}, {}
    for u in final_units:
        ms = unit_mentions(u, lex, masker)
        if occ_units is None:
            for h in ms:
                occ[h] = occ.get(h, 0) + 1
        for h in set(ms):
            docf[h] = docf.get(h, 0) + 1
    for u, w in occ_units or []:
        for h in unit_mentions(u, lex, masker):
            occ[h] = occ.get(h, 0) + w
    if universe is None:
        kmin = cfg["herbs"]["universe_min_passages"]
        universe = sorted(h for h, n in docf.items() if n >= kmin and lex["kind"].get(h) == "herb")
    entries = tangaek_entries(all_units)
    axes, amap = load_axes(cfg)
    msrc = load_meridian_sources(cfg)
    desigs = requisite_designations(all_units)
    sel = select_designations(desigs, requisite_rule, dictionary)
    req_herbs = {}
    for d in sel:
        for h in d["herbs"]:
            c = lex["alias2canon"].get(norm(h))
            if c:
                req_herbs.setdefault(c, []).append(d["indication"])
    tr = tonify_reduce_lists(all_units)

    def canon_list(names):
        return {lex["alias2canon"][norm(n)] for n in names if norm(n) in lex["alias2canon"]}

    if tonify_rule == "large_intestine_tonify":
        ton = canon_list(tr["大腸"]["補用"])
    elif tonify_rule == "large_intestine_tonify_or_reduce":
        ton = canon_list(tr["大腸"]["補用"] + tr["大腸"]["瀉用"])
    elif tonify_rule == "large_intestine_plus_spleen_tonify":
        ton = canon_list(tr["大腸"]["補用"] + tr["脾"]["補用"])
    elif tonify_rule == "none":
        ton = set()
    else:
        raise ValueError(tonify_rule)
    targets = set(cfg["index"]["meridian_targets"])
    fmax = max(occ.get(h, 0) for h in universe) if universe else 1
    rows = []
    for h in universe:
        f = occ.get(h, 0)
        eid, etext = entry_text(h, lex, entries)
        ax = code_axes(etext, axes)
        k = len(ax)
        pats = sorted({p for a in ax for p in amap.get(a, [])})
        dong = donguibogam_channels(etext)
        mer, msource, mcite = None, "none", ""
        for pri in meridian_priority:
            if pri == "Donguibogam":
                if dong:
                    mer, msource, mcite = dong, "Donguibogam", f"Tangaek entry {eid}"
                    break
            else:
                for r in msrc.get(h, []):
                    if r["source"] == pri and r["meridians"].strip():
                        mer, msource, mcite = parse_organs(r["meridians"]), pri, r["citation"]
                        break
                if mer is not None:
                    break
        mer = mer or []
        m_t = len(set(mer) & targets)
        row = dict(herb=h, f=f, passages=docf.get(h, 0),
                   zF=(math.log1p(f) / math.log1p(fmax)) if fmax > 0 else 0.0,
                   k=k, axes="|".join(str(a) for a in sorted(ax)),
                   axis_triggers="; ".join(f"{a}:{'/'.join(v)}" for a, v in sorted(ax.items())),
                   zE=min(k, cfg["index"]["efficacy_cap"]) / cfg["index"]["efficacy_cap"],
                   meridians="".join(mer), meridian_source=msource, meridian_citation=mcite,
                   donguibogam_meridians="".join(dong), m_target=m_t,
                   zM=min(m_t, cfg["index"]["meridian_cap"]) / cfg["index"]["meridian_cap"],
                   requisite="|".join(req_herbs.get(h, [])), zR=1.0 if h in req_herbs else 0.0,
                   patterns="|".join(pats), p=len(pats),
                   zP=min(len(pats), cfg["index"]["pattern_cap"]) / cfg["index"]["pattern_cap"],
                   tonify="yes" if h in ton else "", zT=1.0 if h in ton else 0.0,
                   tangaek_entry=eid or "", flags="")
        flags = []
        if not eid:
            flags.append("no Tangaek entry")
        if msource == "none":
            flags.append("no meridian information in the declared sources (M = 0)")
        elif msource == "Donguibogam":
            flags.append("meridians from the Donguibogam 入經 statement (no textbook or KIOM value)")
        elif msource == "textbook (original analysis record)":
            flags.append("本草學 value as recorded in the original analysis (page not recorded)")
        row["flags"] = "; ".join(flags)
        rows.append(row)
    info = dict(fmax=fmax, designations=desigs, selected=sel, tonify=sorted(ton), tonify_lists=tr,
                occurrences=occ, passage_counts=docf, universe=universe)
    return rows, info


def score(rows, weights):
    keys = ["F", "E", "M", "R", "P", "T"]
    for r in rows:
        r["score"] = sum(weights[k] * r["z" + k] for k in keys)
        for k in keys:
            r["w" + k] = weights[k] * r["z" + k]
    order = sorted(rows, key=lambda r: (-r["score"], r["herb"]))
    for r in rows:
        r["rank"] = 1 + sum(1 for o in order if o["score"] > r["score"] + 1e-9)
    return sorted(rows, key=lambda r: (r["rank"], r["herb"]))
