"""Step 0. Parse the 23 KIOM Donguibogam text files into analysis units.

Unit rules
----------
body   : consecutive ZZ lines under the same lowest heading (AA/BB/CC/DD).
         A prescription, materia medica or acupoint entry ends the block.
presc  : one prescription entry (DP, EP or CP tag) with the SS lines that follow it.
         Where a volume tags prescription content as ZZ instead of SS, ZZ lines that
         directly follow the prescription name (before any SS line) belong to it.
herb   : one materia medica entry of the Tangaek chapter (DH or CH tag) with its SS lines.
acup   : one acupoint entry of the Acupuncture chapter (DK tag) with its SS lines.
XX, TT, PP, Z2, OO and EE lines (author lines, tables, figure labels, contents, special
methods) are appended to the open unit.

unit_id = "<volume>:<first line number>" and is stable as long as the source files are unchanged.
"""
import glob
import os
import re

from common import ROOT, load_config, md5, norm

CHAPTER_CLASS = {"내경편": "clinical", "외형편": "clinical", "잡병편": "clinical",
                 "탕액편": "materia_medica", "침구편": "acupuncture"}
TEXT_DIR_ENV = "DONGUIBOGAM_TEXT_DIR"     # folder of the source files; overrides config "source_text_dir" when set


def source_dir(cfg=None):
    cfg = cfg or load_config()
    return os.path.normpath(os.environ.get(TEXT_DIR_ENV) or os.path.join(ROOT, cfg["source_text_dir"]))


def source_files(cfg=None):
    cfg = cfg or load_config()
    d = source_dir(cfg)
    files = sorted(glob.glob(os.path.join(d, cfg["source_text_glob"])))
    if len(files) != 23:
        raise RuntimeError(f"expected 23 source files ({cfg['source_text_glob']}) in {d}, found {len(files)}")
    return files


def parse(cfg=None):
    units = []
    for p in source_files(cfg):
        book = re.match(r"^동의보감_(.+?)\.txt$", os.path.basename(p)).group(1)    # e.g. 잡병편_권02
        AA = BB = CC = DD = ""
        cur = None
        with open(p, encoding="utf-8") as f:
            for ln, raw in enumerate(f, start=1):
                if raw.startswith("//") or not raw.strip():
                    continue
                m = re.match(r"^([A-Z0-9]{2,3})\t(.*)$", raw.rstrip("\n"))
                if not m:
                    raise ValueError(f"untagged line {p}:{ln}")
                tag, val = m.group(1), m.group(2).strip()
                if tag == "AA":
                    AA, BB, CC, DD, cur = val, "", "", "", None
                    continue
                if tag == "BB":
                    BB, CC, DD, cur = val, "", "", None
                    continue
                if tag == "CC":
                    CC, DD, cur = val, "", None
                    continue
                if tag == "DD":
                    DD, cur = val, None
                    continue

                def new(kind, name, text):
                    u = dict(book=book, AA=AA, BB=BB, CC=CC, DD=DD, type=kind, name=name, text=text,
                             line_start=ln, line_end=ln, n_ss=0)
                    units.append(u)
                    return u

                if tag == "ZZ":
                    if cur is not None and cur["type"] == "presc" and cur["n_ss"] == 0:
                        cur["text"] += (" " if cur["text"] else "") + val
                    elif cur is not None and cur["type"] == "body":
                        cur["text"] += " " + val
                    else:
                        cur = new("body", "", val)
                elif tag in ("DP", "EP", "CP"):
                    cur = new("presc", val, "")
                elif tag in ("DH", "CH"):
                    cur = new("herb", val, "")
                elif tag == "DK":
                    cur = new("acup", val, "")
                elif tag == "SS":
                    if cur is not None and cur["type"] in ("presc", "herb", "acup"):
                        cur["text"] += (" " if cur["text"] else "") + val
                        cur["n_ss"] += 1
                    else:
                        cur = new("presc", "", val)
                        cur["n_ss"] = 1
                else:
                    if cur is not None:
                        cur["text"] += " " + val
                    else:
                        cur = new("body", "", val)
                cur["line_end"] = ln
    for u in units:
        u["unit_id"] = f"{u['book']}:{u['line_start']}"
        u["text"] = u["text"].strip()
        u["chapter_class"] = CHAPTER_CLASS[u["book"].split("_")[0]]
        u["norm"] = norm((u["name"] + " " if u["name"] else "") + u["text"])
        u["norm_text"] = norm(u["text"])
    return units


def source_manifest(cfg=None, digest=md5):
    return {os.path.basename(p): digest(p) for p in source_files(cfg)}
