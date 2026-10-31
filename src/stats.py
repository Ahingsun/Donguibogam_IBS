"""Statistics implemented with numpy only (scipy is not available on this PC)."""
import math

import numpy as np


def rankdata(x):
    """Average ranks (1 = smallest), ties averaged."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def kendall_tau_b(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = len(a)
    conc = disc = ta = tb = 0
    for i in range(n):
        da = np.sign(a[i + 1:] - a[i])
        db = np.sign(b[i + 1:] - b[i])
        prod = da * db
        conc += int((prod > 0).sum())
        disc += int((prod < 0).sum())
        ta += int(((da == 0) & (db != 0)).sum())
        tb += int(((db == 0) & (da != 0)).sum())
    denom = math.sqrt((conc + disc + ta) * (conc + disc + tb))
    return (conc - disc) / denom if denom else float("nan")


def top_k(scores, names, k):
    order = sorted(range(len(names)), key=lambda i: (-scores[i], names[i]))
    return [names[i] for i in order[:k]]


def retention(base_top, alt_top):
    return len(set(base_top) & set(alt_top))


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else float("nan")


def pairwise_flip_rate(a, b):
    """Share of herb pairs whose order differs between score vectors a and b (ties ignored)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n, flips, total = len(a), 0, 0
    for i in range(n):
        da = np.sign(a[i + 1:] - a[i])
        db = np.sign(b[i + 1:] - b[i])
        ok = (da != 0) & (db != 0)
        total += int(ok.sum())
        flips += int((ok & (da != db)).sum())
    return flips / total if total else float("nan")


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - h, c + h


def worst_case_margin(c, w0, delta):
    """min over w of c.w s.t. w0(1-delta) <= w <= w0(1+delta), sum(w) = sum(w0).
    Linear objective over a box cut by one equality: fill the cheapest coordinates first."""
    c, w0 = np.asarray(c, float), np.asarray(w0, float)
    lo, hi = w0 * (1 - delta), w0 * (1 + delta)
    w = lo.copy()
    budget = w0.sum() - lo.sum()
    for i in np.argsort(c):
        add = min(hi[i] - lo[i], budget)
        w[i] += add
        budget -= add
        if budget <= 1e-12:
            break
    return float(c @ w), w


def log_comb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeom_sf(k, M, n, N):
    """P(X >= k), X ~ Hypergeometric(population M, successes n, draws N)."""
    lo, hi = max(k, 0), min(n, N)
    if lo > hi:
        return 0.0
    logs = [log_comb(n, i) + log_comb(M - n, N - i) - log_comb(M, N) for i in range(lo, hi + 1)]
    m = max(logs)
    return float(min(1.0, math.exp(m) * sum(math.exp(x - m) for x in logs)))
