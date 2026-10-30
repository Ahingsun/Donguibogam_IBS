"""Shared helpers: paths, configuration, CSV I/O and text normalization."""
import csv
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # reanalysis_R1/


def path(*parts):
    return os.path.normpath(os.path.join(ROOT, *parts))


def load_config():
    with open(path("config.json"), encoding="utf-8") as f:
        return json.load(f)


def read_csv(rel):
    # Input tables are UTF-8 with a BOM so that Excel opens them with the Hanja intact. A file saved
    # from Excel as plain "CSV" is re-encoded in the ANSI code page, which loses Hanja outside it.
    try:
        with open(path(rel), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except UnicodeDecodeError as e:
        raise SystemExit(f"{rel} is not UTF-8. It was probably saved from Excel as 'CSV'. "
                         f"Save it again as 'CSV UTF-8 (쉼표로 분리)' and rerun. ({e})")


def write_csv(rel, rows, fieldnames=None):
    p = path(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return p


def md5(p, algo="md5"):
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256(p):
    return md5(p, "sha256")


# Variant characters -> one form. Applied to corpus text and to every dictionary/lexicon term
# alike, so that a term matches all spellings found in the Donguibogam text files.
CHAR_MAP = {
    "飧": "飱", "飡": "飱",   # 飱泄
    "祕": "秘",               # 便秘
    "濇": "澁", "澀": "澁",   # 秘澁
    "姙": "妊",               # 妊娠 (the source writes 姙娠)
    "楂": "査",               # 山査
    "洩": "泄",
    "蔻": "蔲",
    "术": "朮",
    "蔘": "參",
    "即": "卽",
    "飲": "飮",
    "欝": "鬱",
    "黏": "粘",
    "胷": "胸",
    "鷄": "雞",
    "后": "後",
    "豬": "猪",
    "糧": "粮",
    "耆": "芪",
    "蘗": "柏",               # 黃蘗 -> 黃柏
    "麯": "麴",
    "鸎": "罌", "甖": "罌",   # 罌粟殼
    "兎": "菟",               # 兎絲子
    "䓀": "桔", "莄": "梗",   # 䓀莄 = 桔梗 (122 times in the Donguibogam text; 甘䓀湯 = 甘桔湯)
}
BIGRAM_MAP = {"藏毒": "臟毒", "彭脹": "膨脹"}


def norm(s):
    for a, b in BIGRAM_MAP.items():
        s = s.replace(a, b)
    return "".join(CHAR_MAP.get(ch, ch) for ch in s)
