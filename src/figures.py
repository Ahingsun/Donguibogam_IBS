"""Figures 1-3 of the article. Fonts: Malgun Gothic for Hanja/Hangul labels."""
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
    fams = [n for n in ("HCR Dotum", "New Gulim", "Malgun Gothic", "Yu Gothic") if n in names]
    if fams:
        plt.rcParams["font.family"] = fams          # first font covering 蔲 朮 參 etc., then fallbacks
    plt.rcParams["axes.unicode_minus"] = False


def flow(counts, out):
    _font()
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.axis("off")
    div = counts.get("divided")          # passages divided at source citations into adjudication units
    n_units = counts.get("adjudicated_units", counts["adjudicated"])
    boxes = [
        (0.5, 0.92, f"Clinical chapters of Donguibogam\n(Naegyeong, Oehyeong, Japbyeong)\nn = {counts['units']:,} passages"),
        (0.5, 0.72, f"Keyword score ≥ {counts['threshold']}\nn = {counts['candidates']}"),
        (0.5, 0.51, f"After the exclusion filter\nn = {counts['adjudicated']} passages" +
         (f"\n({div} divided at source citations:\n{n_units} adjudication units)" if div else "")),
        (0.5, 0.28, f"Included by content adjudication\nn = {counts['included']}" +
         (f" units\n(from {counts['included_passages']} passages)" if div else "") +
         (f"\ntier 1 (Rome IV core) {counts['tier1']}, tier 2 {counts['tier2']}" if "tier1" in counts else "")),
    ]
    side = [
        (0.88, 0.82, f"Score < {counts['threshold']}\nn = {counts['units'] - counts['candidates']:,}"),
        (0.88, 0.62, f"Excluded by filter\nn = {counts['filtered']}"),
        (0.88, 0.40, f"Excluded at adjudication\nn = {n_units - counts['included']}" + (" units" if div else "")),
    ]
    for x, y, t in boxes:
        ax.text(x, y, t, ha="center", va="center", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black"))
    for x, y, t in side:
        ax.text(x, y, t, ha="center", va="center", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="#F2F2F2", ec="gray"))
    for (x0, y0, _), (x1, y1, _) in zip(boxes[:-1], boxes[1:]):
        ax.annotate("", xy=(x1, y1 + 0.06), xytext=(x0, y0 - 0.07), arrowprops=dict(arrowstyle="->"))
    for (x, y, _), (sx, sy, _) in zip(boxes[:-1], side):
        ax.annotate("", xy=(0.68, sy), xytext=(x, sy), arrowprops=dict(arrowstyle="->", color="gray"))
    if counts.get("note"):
        ax.text(0.5, 0.12, counts["note"], ha="center", va="center", fontsize=8, color="dimgray", wrap=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def contributions(base_rows, out, top=20):
    _font()
    ranked = sorted(base_rows, key=lambda r: (r["rank"], r["herb"]))[:top][::-1]
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * top + 1.2))
    left = [0.0] * len(ranked)
    for k in KEYS:
        vals = [r["w" + k] for r in ranked]
        ax.barh([r["herb"] for r in ranked], vals, left=left, color=COLORS[k], label=LABELS[k])
        left = [a + b for a, b in zip(left, vals)]
    for i, r in enumerate(ranked):
        ax.text(left[i] + 0.8, i, f"{r['score']:.1f}", va="center", fontsize=8)
    ax.set_xlabel("Index score (sum of weighted components; maximum 100)")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=7, loc="lower right", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def rank_stability(rank_table, herbs, out):
    """rank_table: {scenario: {herb: rank}}; herbs: primary order (top-N)."""
    _font()
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(herbs) + 1.2))
    scen = list(rank_table)
    for i, h in enumerate(herbs[::-1]):
        rs = [rank_table[s][h] for s in scen if h in rank_table[s]]
        ax.plot([min(rs), max(rs)], [i, i], color="lightgray", lw=4, solid_capstyle="round")
        ax.plot(rank_table[scen[0]][h], i, "o", color="black", ms=4)
    ax.set_yticks(range(len(herbs)))
    ax.set_yticklabels(herbs[::-1])
    ax.invert_xaxis()
    ax.set_xlabel("Rank (dot: primary; bar: range across sensitivity scenarios)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
