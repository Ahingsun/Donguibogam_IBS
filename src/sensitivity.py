"""Step 8. Sensitivity analyses and diagnostics of the herb index.

All comparisons are against the primary ranking and describe internal stability only.
"""
import copy
import math

import numpy as np

import stats
from features import score

KEYS = ["F", "E", "M", "R", "P", "T"]


def weights_scenarios(w0, cfg):
    base = dict(w0)
    total = sum(base.values())

    def rescale(fixed_key, fixed_val):
        rest = {k: v for k, v in base.items() if k != fixed_key}
        s = sum(rest.values())
        out = {k: v * (total - fixed_val) / s for k, v in rest.items()}
        out[fixed_key] = fixed_val
        return out

    sc = [("primary (25/25/15/15/10/10)", base),
          ("equal weights (100/6 each)", {k: total / 6 for k in KEYS}),
          ("frequency down (F = 10, others rescaled)", rescale("F", 10)),
          ("efficacy up (E = 35, others rescaled)", rescale("E", 35)),
          ("requisite removed (R = 0)", {**base, "R": 0})]
    d = cfg["sensitivity"]["perturbation"]
    for seed in cfg["sensitivity"]["random_seeds"]:
        rng = np.random.default_rng(seed)
        f = rng.uniform(1 - d, 1 + d, size=6)
        w = {k: base[k] * f[i] for i, k in enumerate(KEYS)}
        s = sum(w.values())
        sc.append((f"random ±{int(d * 100)}% (seed {seed})", {k: v * total / s for k, v in w.items()}))
    return sc


def compare(base_rows, alt_rows, label, ks=(10, 20)):
    bmap = {r["herb"]: r["score"] for r in base_rows}
    amap = {r["herb"]: r["score"] for r in alt_rows}
    common = sorted(set(bmap) & set(amap))
    a = [bmap[h] for h in common]
    b = [amap[h] for h in common]
    out = dict(analysis=label, n_herbs=len(common), spearman=round(stats.spearman(a, b), 3),
               kendall_tau_b=round(stats.kendall_tau_b(a, b), 3),
               pairwise_flip_rate=round(stats.pairwise_flip_rate(a, b), 3))
    for k in ks:
        bt = stats.top_k([bmap[h] for h in bmap], list(bmap), k)
        at = stats.top_k([amap[h] for h in amap], list(amap), k)
        out[f"top{k}_retained"] = f"{stats.retention(bt, at)}/{k}"
        out[f"top{k}_jaccard"] = round(stats.jaccard(bt, at), 3)
    return out


def weight_sensitivity(rows, cfg):
    w0 = cfg["index"]["weights"]
    base = score(copy.deepcopy(rows), w0)
    res = []
    for label, w in weights_scenarios(w0, cfg):
        alt = score(copy.deepcopy(rows), w)
        r = compare(base, alt, label)
        r["weights"] = " ".join(f"{k}={w[k]:.1f}" for k in KEYS)
        res.append(r)
    # distribution over many random perturbations
    rng = np.random.default_rng(cfg["sensitivity"]["random_draws_seed"])
    d = cfg["sensitivity"]["perturbation"]
    rhos, t10 = [], []
    bscores = [r["score"] for r in sorted(base, key=lambda x: x["herb"])]
    bt10 = stats.top_k([r["score"] for r in base], [r["herb"] for r in base], 10)
    for _ in range(cfg["sensitivity"]["random_draws"]):
        f = rng.uniform(1 - d, 1 + d, size=6)
        w = {k: w0[k] * f[i] for i, k in enumerate(KEYS)}
        alt = score(copy.deepcopy(rows), w)
        ascores = [r["score"] for r in sorted(alt, key=lambda x: x["herb"])]
        rhos.append(stats.spearman(bscores, ascores))
        t10.append(stats.retention(bt10, stats.top_k([r["score"] for r in alt], [r["herb"] for r in alt], 10)))
    dist = dict(analysis=f"{cfg['sensitivity']['random_draws']} random ±{int(d * 100)}% draws (seed {cfg['sensitivity']['random_draws_seed']})",
                spearman_median=round(float(np.median(rhos)), 3), spearman_p05=round(float(np.percentile(rhos, 5)), 3),
                spearman_min=round(float(np.min(rhos)), 3),
                top10_retained_median=float(np.median(t10)), top10_retained_min=int(np.min(t10)))
    return base, res, dist


def ablation(rows, cfg):
    w0 = cfg["index"]["weights"]
    base = score(copy.deepcopy(rows), w0)
    out = []
    for k in KEYS:
        w = {**w0, k: 0}
        alt = score(copy.deepcopy(rows), w)
        out.append(compare(base, alt, f"without {k}"))
    return out


def worst_case_margins(base_rows, cfg, top=20):
    w0 = np.array([cfg["index"]["weights"][k] for k in KEYS], float)
    ranked = sorted(base_rows, key=lambda r: r["rank"])
    z = {r["herb"]: np.array([r["z" + k] for k in KEYS]) for r in base_rows}
    out = []
    pairs = [(ranked[i]["herb"], ranked[i + 1]["herb"]) for i in range(min(top, len(ranked) - 1))]
    if len(ranked) > 10:
        pairs += [(ranked[i]["herb"], ranked[10]["herb"]) for i in range(10)]
    seen = set()
    for hi, hj in pairs:
        if (hi, hj) in seen:
            continue
        seen.add((hi, hj))
        c = z[hi] - z[hj]
        row = dict(herb_i=hi, herb_j=hj, rank_i=next(r["rank"] for r in ranked if r["herb"] == hi),
                   rank_j=next(r["rank"] for r in ranked if r["herb"] == hj), base_margin=round(float(c @ w0), 2))
        for d in cfg["sensitivity"]["worst_case_deltas"]:
            L, _ = stats.worst_case_margin(c, w0, d)
            row[f"worst_margin_delta{int(d * 100)}"] = round(L, 2)
            row[f"order_guaranteed_delta{int(d * 100)}"] = "yes" if L > 0 else "no"
        out.append(row)
    return out


def design_matrix(rows):
    Z = np.array([[r["z" + k] for k in KEYS] for r in rows], float)
    rng_rows = [dict(component=k, min=round(float(Z[:, i].min()), 3), max=round(float(Z[:, i].max()), 3),
                     mean=round(float(Z[:, i].mean()), 3), distinct_values=len(set(np.round(Z[:, i], 6))))
                for i, k in enumerate(KEYS)]
    corr = []
    for i, a in enumerate(KEYS):
        corr.append({"component": a, **{b: round(stats.spearman(Z[:, i], Z[:, j]), 3) for j, b in enumerate(KEYS)}})
    sd = Z.std(axis=0)
    keep = sd > 0
    Zs = (Z[:, keep] - Z[:, keep].mean(axis=0)) / sd[keep]
    sv = np.linalg.svd(Zs, compute_uv=False)
    diag = dict(n_herbs=len(rows), rank=int(np.linalg.matrix_rank(Zs)),
                singular_values=" ".join(f"{x:.3f}" for x in sv),
                condition_number=round(float(sv[0] / sv[-1]), 2) if sv[-1] > 0 else float("inf"),
                scaling="centered and divided by SD (z-scores)")
    return rng_rows, corr, diag


def contributions(base_rows, tops=(10, 20)):
    """Weighted components of the herbs ranked t-th or higher; herbs tied at the boundary are all included."""
    out = []
    ranked = sorted(base_rows, key=lambda r: (r["rank"], r["herb"]))
    for t in tops:
        sub = [r for r in ranked if r["rank"] <= t]
        tot = sum(r["score"] for r in sub)
        for k in KEYS:
            v = [r["w" + k] for r in sub]
            out.append(dict(top=t, n_herbs=len(sub), component=k, mean=round(float(np.mean(v)), 2), min=round(float(np.min(v)), 2),
                            max=round(float(np.max(v)), 2), share_of_total=round(sum(v) / tot, 3) if tot else ""))
    return out


def tfidf_variant(rows, corpus_doc_counts, n_docs):
    alt = copy.deepcopy(rows)
    xs = {}
    for r in alt:
        df = max(1, corpus_doc_counts.get(r["herb"], 1))
        xs[r["herb"]] = math.log1p(r["f"]) * math.log(n_docs / df)
    xmax = max(xs.values()) if xs else 1
    for r in alt:
        r["zF"] = xs[r["herb"]] / xmax if xmax > 0 else 0.0
        r["idf"] = round(math.log(n_docs / max(1, corpus_doc_counts.get(r["herb"], 1))), 3)
    return alt


def enrichment(rows, ibs_doc_counts, corpus_doc_counts, n_ibs, n_docs):
    out = []
    for r in rows:
        h = r["herb"]
        k, K = ibs_doc_counts.get(h, 0), corpus_doc_counts.get(h, 0)
        ratio = (k / n_ibs) / (K / n_docs) if K else float("nan")
        out.append(dict(herb=h, ibs_passages=k, corpus_units=K, share_ibs=round(k / n_ibs, 4),
                        share_corpus=round(K / n_docs, 4), log2_enrichment=round(math.log2(ratio), 3) if ratio > 0 else "",
                        p_hypergeom=stats.hypergeom_sf(k, n_docs, K, n_ibs)))
    m = len(out)
    order = sorted(range(m), key=lambda i: out[i]["p_hypergeom"])
    prev = 1.0
    for rank_i, i in reversed(list(enumerate(order, 1))):     # Benjamini-Hochberg
        q = min(prev, out[i]["p_hypergeom"] * m / rank_i)
        out[i]["q_bh"] = q
        prev = q
    for r in out:
        r["p_hypergeom"] = float(f"{r['p_hypergeom']:.3g}")
        r["q_bh"] = float(f"{r['q_bh']:.3g}")
    return sorted(out, key=lambda r: (r["q_bh"], r["herb"]))


def kiom_comparison(rows, msrc, targets, cfg):
    """Agreement between Donguibogam 入經 statements and KIOM monograph meridians, and the
    chance level of 'overlap with the six target meridians'."""
    from features import parse_organs
    pairs, overlap6 = [], []
    for r in rows:
        k = [x for x in msrc.get(r["herb"], []) if x["source"] == "KIOM monograph"]
        if not k:
            continue
        km = set(parse_organs(k[0]["meridians"]))
        dm = set(r["donguibogam_meridians"] and parse_organs(r["donguibogam_meridians"]) or [])
        overlap6.append((r["herb"], km))
        if dm:
            pairs.append((r["herb"], dm, km))
    rng = np.random.default_rng(cfg["sensitivity"]["kiom_permutation_seed"])
    organs12 = ["肝", "心", "脾", "肺", "腎", "心包", "膽", "小腸", "胃", "大腸", "膀胱", "三焦"]
    obs6 = np.mean([1.0 if (km & set(targets)) else 0.0 for _, km in overlap6]) if overlap6 else float("nan")
    sims = []
    for _ in range(cfg["sensitivity"]["kiom_permutations"]):
        hits = 0
        for _, km in overlap6:
            draw = set(rng.choice(organs12, size=len(km), replace=False)) if km else set()
            hits += 1 if draw & set(targets) else 0
        sims.append(hits / len(overlap6) if overlap6 else float("nan"))
    jac = [stats.jaccard(d, k) for _, d, k in pairs]
    obs_j = float(np.mean(jac)) if jac else float("nan")
    perm = []
    ks = [k for _, _, k in pairs]
    for _ in range(cfg["sensitivity"]["kiom_permutations"]):
        idx = rng.permutation(len(ks))
        perm.append(np.mean([stats.jaccard(pairs[i][1], ks[idx[i]]) for i in range(len(ks))]))
    summary = dict(
        herbs_with_kiom=len(overlap6),
        overlap_with_6_targets_observed=round(obs6, 3) if overlap6 else "",
        overlap_with_6_targets_chance_mean=round(float(np.mean(sims)), 3) if sims else "",
        herbs_with_both_sources=len(pairs),
        donguibogam_vs_kiom_mean_jaccard=round(obs_j, 3) if jac else "",
        permutation_mean_jaccard=round(float(np.mean(perm)), 3) if perm else "",
        permutation_p=round(float((np.sum(np.array(perm) >= obs_j) + 1) / (len(perm) + 1)), 4) if perm else "")
    detail = [dict(herb=h, donguibogam="".join(sorted(d)), kiom="".join(sorted(k)),
                   jaccard=round(stats.jaccard(d, k), 3)) for h, d, k in pairs]
    return summary, detail
