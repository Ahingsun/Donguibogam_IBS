#!/usr/bin/env bash
# Reproduce the published N=162 corpus and Table-4 herb ranking.
# Usage: ./run_all.sh /path/to/folder_with_donguibogam_txt
set -euo pipefail
DATA="${1:?Provide the path to the folder containing 동의보감_*.txt}"

echo "== [1/2] front-end: parse + keyword scoring -> candidates (reference) =="
python3 src/ibs_pipeline.py --corpus "$DATA/동의보감_*.txt" \
        --keywords data/keyword_dictionary_180.csv \
        --intrinsic data/herb_intrinsic_scores.csv

echo; echo "== [2/2] authoritative: adjudication -> N=162 + Table 4 =="
python3 src/reproduce_n162.py   # needs no corpus; uses committed adjudication + scores

echo; echo "Outputs in results/: n162_corpus.csv, exclusions_177.csv, table4_herb_ranking.csv"
