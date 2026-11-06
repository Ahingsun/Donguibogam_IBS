# Donguibogam IBS: text-based prioritization of herbs and formulas

Analysis code for Lee I.-S., Jung J. H., Lee Y. J., Han Y. J., Kim J. and Ha N.-Y., "A traditional medicine text-based algorithm for prioritizing candidate herbs and prescriptions for Irritable Bowel Syndrome-related symptoms" (revised manuscript, Scientific Reports).

## Contents

- `run_all.py` runs the passage screening and exclusion filter, reads the adjudication record, and computes the herb index, the formula scores, the acupoint summary and the sensitivity analyses.
- `run_d2.py` analyzes the independent rating (agreement, precision and recall).
- `src/` holds the modules both scripts use.
- `config.json` holds the parameters, weights and random seeds.

## Inputs (not included)

- The Donguibogam source text, 23 volumes of tagged plain text, can be obtained from the Korean Medicine Classics Database of the Korea Institute of Oriental Medicine (https://www.mediclassics.kr) under its terms of use. Put the files in `source_texts/`.
- The curated input tables, the adjudication record and the independent ratings are available from the corresponding author on reasonable request. Put them in `data/`, `decisions/` and `d2/` under the names given in `config.json`.


## Running

Python 3.14 with the packages in `requirements.txt`, then

    python run_d2.py analyze
    python run_all.py

The results are written to `outputs/`.

## License

MIT (see `LICENSE`).
