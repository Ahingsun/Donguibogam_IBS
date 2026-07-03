# Reproducibility package — DGBG-IBS

Supplementary data and code for *"A Donguibogam-Based Algorithm for Prioritizing
Candidate Herbs and Prescriptions for Irritable Bowel Syndrome."*

This package makes every step from raw text to herb ranking reproducible, with **no
subjective expert selection step**. It is referenced by the manuscript's Data Sharing
Statement.

## Contents

| File | What it is |
|---|---|
| `ibs_pipeline.py` | Reference implementation: parses the 23 source files, scores passages with the keyword dictionary, documents the I-1..I-3 / E-1..E-7 inclusion/exclusion criteria, and computes the DGBG-IBS herb ranking (6-component weighted sum, max 100). |
| `keyword_dictionary.csv` | The full inclusion keyword list with ROME IV category mapping and retrieved/excluded passage counts (manuscript Table 1). |
| `herb_intrinsic_scores.csv` | Per-herb DGBG components. The **75 corpus-independent points** (efficacy 25 + meridian 15 + must-use/序例 15 + pattern 10 + tonify 10) plus the published corpus frequency and total score. |
| `../동의보감_IBS_조문선정_확정.xlsx` | The passage-by-passage adjudication of all candidates: sheet `01_전수판정_339` gives, for every passage, the keyword score, source 門, ROME IV subtype/grade, and the final **유지 (keep) / 제외 (exclude)** decision with rationale (162 keep / 177 exclude). |
| `IBS조문_선정제외기준_확정_2026-06-18.md` (in parent folder) | The formal inclusion (I-1–I-3) and exclusion (E-1–E-7) criteria. |

## How to run

```bash
cd reproducibility
python ibs_pipeline.py            # expects the 23 *.txt in ../../동의보감_IBS/
```

## Scoring (manuscript Table 2)

```
DGBG-IBS = frequency(25) + efficacy(25) + meridian(15) + must-use 序例(15)
           + pattern(10) + tonify(10)            # weighted sum, max 100
frequency(25) = 25 * ln(1+f) / ln(1+f_max)       # f = occurrences in the IBS corpus
Prescription score = mean DGBG of constituent herbs (an unscored herb contributes 0).
```

The eight IBS efficacy axes are: 止瀉澁腸, 溫中散寒, 行氣止痛, 消食化積, 健脾益氣,
燥濕化濕, 潤腸通便, 疏肝理氣. Meridian match is over 脾·胃·大腸·小腸·肝·腎.
"Must-use (須用)" is a direct symptom→herb designation in the Tangaek (Decoctions)
preface (序例) — e.g. 腹痛須用芍藥, 腹脹須用厚朴, 水瀉須用白朮·茯苓 — and is distinct from
引經 (meridian-guiding).

## Passage selection (content-based, reproducible)

`9,100 passage units → 434 keyword-positive candidates (score ≥ 3) → 272 excluded → n = 162`

A passage is **included** only if a chronic/functional bowel symptom is its chief
complaint (I-1) and the pattern fits an IBS bian-zheng frame (I-2); the source 門 is not
a criterion (I-3 — judged by content, not section). It is **excluded** under any of
E-1 pre-registered categories (parasite / epidemic / acute 霍亂 / pregnancy 姙娠·産後 /
痘瘡·麻疹 / anorectal-organic 痔·脫肛·腸癰·藏毒·腸風 / acute 噤口·暴痢), E-2 pediatric (小兒),
E-3 acute febrile 傷寒·暑 (except chronic 虛寒 formulae 理中湯類·眞武湯), E-4 incidental
keyword match, E-5 pure theory/pulse, E-6 abdominal pain without defecation linkage,
E-7 systemic disease with incidental diarrhea.

**Variant-character normalization is applied to both the inclusion and the exclusion
sides** (飱↔飧↔飡, 秘↔祕, 姙↔妊, 藏↔臟); a post-hoc audit of the published corpus found the
original run had normalized only the inclusion side, which this pipeline corrects.

## Note on unit granularity (honest reproducibility caveat)

The published pipeline aggregates the text to **9,100 passage units**; the reference
script here counts finer tag-level units (~20,888 ZZ/SS/DK segments), so its raw
candidate count (~540) is larger than the published 434. This affects only the size of
the candidate pool, **not the herb ranking**: the reference run reproduces the published
Top-10 (木香, 厚朴, 白朮, 肉豆蔲, 黃連, 芍藥, 草豆蔲, 茯苓, 枳實, 陳皮). The herb ranking is
dominated by the 75 corpus-independent points, which is why it is robust to corpus and
threshold perturbations (Spearman ρ ≥ 0.90 throughout; see manuscript Robustness).

## Source data

Donguibogam source texts: KIOM Korean Medicine Classics Database (Mediclassics),
https://www.mediclassics.kr — publicly available.
