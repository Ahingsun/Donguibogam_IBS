# Donguibogam IBS: analysis code and data

Code and data for the revised manuscript "A traditional medicine text-based algorithm for prioritizing candidate
herbs and prescriptions for Irritable Bowel Syndrome". Two scripts reproduce every result of the article from the
Donguibogam text files and the tables in this repository.

## Source text

Put the Donguibogam text files (.txt) in `source_texts/`.

## Running

```
python -m pip install -r requirements.txt
python run_d2.py analyze     # independent rating: agreement, precision and recall
python run_all.py            # screening, adjudication record, herb index, sensitivity analyses, formulas, acupoints, figures
```

`run_d2.py analyze` writes `d2/d2_summary.json` and `d2/d2_per_unit.csv`. `run_all.py` rewrites `outputs/`, takes about
a minute and reads `d2/d2_per_unit.csv` for the two sensitivity corpora that add the units both raters judged
relevant, so it runs second. The files in this repository were produced with Python 3.14.7, NumPy 2.5.3, openpyxl 3.1.5 and
Matplotlib 3.11.2, and running the two scripts on the text files listed in `source_texts/README.md` reproduces them.
Columns that would quote the source text are left out of the outputs (`config.json`,
`"outputs": {"source_text": false}`).

## Contents

| Path | Contents |
|---|---|
| `run_all.py`, `src/` | The analysis, one module per step (corpus parsing, screening, adjudication, herb features and index, sensitivity analyses, formula composition, acupoints, figures). |
| `run_d2.py`, `src/d2.py` | Analysis of the independent rating of a stratified random sample. |
| `config.json` | Threshold, weights, caps, seeds and file locations. |
| `data/` | Curated input tables: screening dictionary with term weights and Rome V domains, exclusion terms, herb alias dictionary, Latin names, efficacy axes and trigger terms, axis–pattern map, pattern terms, meridian sources, acupoint names with WHO codes, guideline acupoints. |
| `data/old_analysis/` | Decisions and herb ranking of the analysis in the originally submitted manuscript, used for the comparison with the submitted ranking. |
| `decisions/adjudication_record.csv` | The decision for every candidate unit (below). |
| `d2/` | Sampling design (`design.json`), rating key (`rating_key.csv`: rating id, unit, stratum, inclusion probability) and the include/exclude answers of the two raters (`ratings.csv`; 포함 include, 제외 exclude, blank no answer), with the first author's label for the units on which they disagreed (`author_label`). The primary estimates use the units on which the raters agreed. Precision and recall are stratum-weighted (Horvitz–Thompson) estimates for the clinical chapters, and `d2_summary.json` gives them for each step of the procedure under `steps` (screen: keyword score at or above the threshold; filter: also not removed by the exclusion filter; final: included after adjudication) and with the author's labels under `with_author_labels`. |
| `outputs/` | All results (below). |

## Adjudication record

One row per candidate unit. A body passage that joins excerpts from two or more sources is judged by source unit.

| Column | Meaning |
|---|---|
| 번호 | Number of the unit; `n-k` is the k-th source unit of passage n |
| unit_id | `<volume>:<first line>` in the source file; `#k` marks the k-th source unit |
| 편·권, 門, 소분류, 세부 | Volume, section, subsection and heading |
| 유형, 처방명 | Body text (본문) or prescription (처방), and the prescription name |
| 최종판정 | Decision: 포함 (included) or 제외 (excluded) |
| 포함근거 | Inclusion criteria met (I-1a to I-3) |
| 제외코드 | Exclusion criteria (E-1 to E-9) |
| R4_배변연관통증, R4_빈도변화, R4_형태변화, R4_만성표지 | Y or N: abdominal pain associated with defecation or written together with a change in bowel habit; change in stool frequency; change in stool form; explicit marker of chronicity |
| 배변양상 | Bowel habit: 설사 diarrhea, 변비 constipation, 혼합 mixed, 미분류 unclassified |

The criteria are defined in the Methods of the article and in `src/adjudication.py` (`INCLUDE_CODES`,
`EXCLUDE_CODES`). An included unit is tier 1 when R4_배변연관통증 is Y together with R4_빈도변화 or R4_형태변화,
and tier 2 otherwise.

## Outputs

| File | Contents |
|---|---|
| `01_screening_all_clinical_units.csv` | Screening score, matched terms and filter result of every unit of the clinical chapters |
| `02_adjudication_status.csv` | Decision, tier, bowel habit and patterns of every candidate unit |
| `03_final_passages.csv` | Included units with their keyword-level Rome elements |
| `04_herb_index.csv` | The six components, the weighted contributions and the score of every herb |
| `05`–`07` | Requisite designations, tonify and reduce lists, meridian source of every herb |
| `10`–`19` | Weight scenarios, random weight draws, ablation, worst-case pairwise margins, design-matrix diagnostics, component contributions, alternative rules and corpora, enrichment |
| `20`–`22` | Comparison with the KIOM monographs and with the ranking of the submitted manuscript |
| `30`–`32` | Formulas and their scores, overall and by bowel habit and pattern |
| `40`–`41` | Acupuncture and moxibustion statements and the points they name |
| `fig1`, `fig2` | Figures 1 and 2 |
| `fig3` | Supplementary Figure S1 |
| `manifest.json`, `run_log.txt` | Checksums of the source files, inputs and code, library versions, seeds, counts and the log of the run |
| `결과요약_R1.xlsx` | All CSV outputs in one workbook |

## License

MIT (`LICENSE`). The license covers the code and the tables in this repository. It does not cover the text of
Donguibogam, which is not included.
