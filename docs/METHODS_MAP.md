# Manuscript ↔ Code map

| Manuscript (Methods/Results) | Implementation |
|---|---|
| Full-text structuring at chapter/section/subcategory/detail | `parse_corpus.py` (AA/BB/CC hierarchy tags; all 23 volumes) |
| ROME IV–anchored keyword dictionary (Table 1) | `data/keyword_dictionary.json` (+ variant map in `config.json`) |
| Keyword score, ≥3 candidates | `pipeline.py` → `kwscore()`, `candidates` |
| Pre-registered inclusion/exclusion (parasite, epidemic, cholera, pregnancy, smallpox, anorectal, acute dysentery, bloody-purulent unless chronic) | `config.json["exclusion"]` + `keep()` |
| IBS 8-axis efficacy (止瀉澁腸 … 疏肝理氣) | `config.json["efficacy_axes"]`, matched in `build_herb_db.py` |
| Must-use herbs (諸經引導 preface) | `build_herb_db.py` → `must_use.json` |
| Meridian tropism 脾胃大腸小腸肝腎 | `config.json["meridian_targets"]` + `data/meridian_overrides.json` (OASIS) |
| Six-component weighted score (Table 2) | `pipeline.py` → `comp()` |
| TF-IDF IBS-specificity correction | `pipeline.py` → `idf()`, `rho_tfidf` |
| Weight sensitivity (Spearman ρ across scenarios) | `pipeline.py` → `W`, `sens` |
