# experimental/ — NOT the authoritative reproduction

These scripts are an **independent, from-scratch re-implementation** built to sanity-check
the method directly from the raw sources. They do **not** reproduce the published numbers
exactly and must not be cited as the reproduction — use `../src/reproduce_n162.py` for that.

- `pipeline_from_scratch.py` — parses all 23 volumes, keyword-scores, applies rule-only
  inclusion/exclusion, and derives a 6-component herb score end-to-end. Produces ballpark
  numbers (candidates ~365, corpus ~320) and a herb ranking whose TOP is consistent with the
  paper (木香/白朮/茯苓/厚朴/黃連/芍藥). Useful as a method cross-check.
- `derive_herb_scores_from_source.py` — roadmap toward computing the 75 corpus-independent
  points (efficacy 8-axis, 序例 must-use, tonification) from the Tangaek chapter, so that
  `herb_intrinsic_scores.csv` becomes *generated* rather than *asserted*. Meridian tropism
  still needs the OASIS monographs (see `meridian_overrides.json`).
- `config_from_scratch.json`, `keyword_dictionary_124_from_docx.json`, `meridian_overrides.json`
  — supporting dictionaries for the above.

Roadmap (deferred, changes numbers → to be reconciled with the manuscript):
execute E-1..E-3 as code, fix substring herb-matching, unify the frequency definition,
and regenerate the 75 points from source.
