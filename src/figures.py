"""Figures 1-3 of the article. Herbs are labelled by their pharmacopoeial Latin names (data/latin_names.csv, the
names used in the article; researcher request 2026-10-27: no Chinese characters in the figures), falling back to the
Chinese name for a herb without one. Fonts: Arial or DejaVu Sans, with a CJK font only as a glyph fallback."""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

KEYS = ["F", "E", "M", "R", "P", "T"]
LABELS = {"F": "Frequency (25)", "E": "Efficacy (25)", "M": "Meridian affinity (15)",
          "R": "Requisite designation (15)", "P": "Pattern coverage (10)", "T": "Large-intestine tonification (10)"}
COLORS = {"F": "#4C78A8", "E": "#F58518", "M": "#54A24B", "R": "#E45756", "P": "#B279A2", "T": "#9D755D"}


def _font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    fams = [n for n in ("Arial", "DejaVu Sans", "Malgun Gothic", "Yu Gothic") if n in names]
    if fams:
        plt.rcParams["font.family"] = fams          # Latin first; a CJK font only for a glyph the others lack
    plt.rcParams["axes.unicode_minus"] = False


def latin_labels():
    """herb -> Latin name from data/latin_names.csv (the herb itself when it has none)."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "latin_names.csv")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8-sig") as f:
        return {r["herb"]: r["latin"] for r in csv.DictReader(f) if r["latin"]}


def flow(counts, out):
    _font()
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.axis("off")
    div = counts.get("divided")          # passages divided at source citations into adjudication units
    n_units = counts.get("adjudicated_units", counts["adjudicated"])
    mx, sx = 0.36, 0.84                  # centres of the main column and of the side column
    boxes = [
        (mx, 0.92, f"Clinical chapters of Donguibogam\n(Naegyeong, Oehyeong, Japbyeong)\nn = {counts['units']:,} passages"),
        (mx, 0.72, f"Keyword score ≥ {counts['threshold']}\nn = {counts['candidates']}"),
        (mx, 0.51, f"After the exclusion filter\nn = {counts['adjudicated']} passages" +
         (f"\n({div} divided at source citations:\n{n_units} adjudication units)" if div else "")),
        (mx, 0.28, f"Included by content adjudication\nn = {counts['included']}" +
         (f" units\n(from {counts['included_passages']} passages)" if div else "") +
         (f"\ntier 1 (Rome IV core) {counts['tier1']}, tier 2 {counts['tier2']}" if "tier1" in counts else "")),
    ]
    side = [
        (sx, 0.82, f"Score < {counts['threshold']}\nn = {counts['units'] - counts['candidates']:,}"),
        (sx, 0.62, f"Excluded by filter\nn = {counts['filtered']}"),
        (sx, 0.40, f"Excluded at adjudication\nn = {n_units - counts['included']}" + (" units" if div else "")),
    ]
    for x, y, t in boxes:
        ax.text(x, y, t, ha="center", va="center", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black"))
    side_text = [ax.text(x, y, t, ha="center", va="center", fontsize=9,
                         bbox=dict(boxstyle="round,pad=0.4", fc="#F2F2F2", ec="gray")) for x, y, t in side]
    for (x0, y0, _), (x1, y1, _) in zip(boxes[:-1], boxes[1:]):
        ax.annotate("", xy=(x1, y1 + 0.06), xytext=(x0, y0 - 0.07), arrowprops=dict(arrowstyle="->"))
    for (x, _, _), (_, sy, _), st in zip(boxes[:-1], side, side_text):
        # the arrow ends at the left edge of the side box (coordinates relative to the box)
        ax.annotate("", xy=(0, 0.5), xycoords=st, xytext=(x, sy), textcoords="data",
                    arrowprops=dict(arrowstyle="->", color="gray", shrinkB=6))
    if counts.get("note"):
        ax.text(mx, 0.12, counts["note"], ha="center", va="center", fontsize=8, color="dimgray", wrap=True)
    # limits around the drawn boxes, so that the saved figure carries no empty margin
    ax.set_xlim(0.06, 1.02)
    ax.set_ylim(0.05 if counts.get("note") else 0.17, 1.0)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def contributions(base_rows, out, top=20, labels=None):
    _font()
    lab = labels or {}
    ranked = sorted(base_rows, key=lambda r: (r["rank"], r["herb"]))[:top][::-1]
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * top + 1.2))
    left = [0.0] * len(ranked)
    for k in KEYS:
        vals = [r["w" + k] for r in ranked]
        ax.barh([lab.get(r["herb"], r["herb"]) for r in ranked], vals, left=left, color=COLORS[k], label=LABELS[k])
        left = [a + b for a, b in zip(left, vals)]
    for i, r in enumerate(ranked):
        ax.text(left[i] + 0.8, i, f"{r['score']:.1f}", va="center", fontsize=8)
    ax.set_xlabel("Index score (sum of weighted components; maximum 100)")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=7, loc="lower right", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def rank_stability(rank_table, herbs, out, labels=None):
    """rank_table: {scenario: {herb: rank}}; herbs: primary order (top-N)."""
    _font()
    lab = labels or {}
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(herbs) + 1.2))
    scen = list(rank_table)
    for i, h in enumerate(herbs[::-1]):
        rs = [rank_table[s][h] for s in scen if h in rank_table[s]]
        ax.plot([min(rs), max(rs)], [i, i], color="lightgray", lw=4, solid_capstyle="round")
        ax.plot(rank_table[scen[0]][h], i, "o", color="black", ms=4)
    ax.set_yticks(range(len(herbs)))
    ax.set_yticklabels([lab.get(h, h) for h in herbs[::-1]])
    ax.invert_xaxis()
    ax.set_xlabel("Rank (dot: primary; bar: range across sensitivity scenarios)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
