"""Step 4. Automatic passage flags used to pre-fill the researcher's workbook and to stratify results.

These are keyword flags, not judgments. The researcher confirms or corrects them in the workbook.
"""
import re

from common import load_config, norm, read_csv

CHRONIC_RX = re.compile(r"久泄|久痢|久瀉|休息痢|五更|經年|累年|數年|積年|連年|多年|日久|年久|屢|反復|乍發乍止|時作時止|或作或止|不愈|久不|三五年")
ACUTE_RX = re.compile(r"傷寒|中暑|暑月|暑泄|瘧|疫|壯熱|發熱")
SYSTEMIC_RX = re.compile(r"水腫|浮腫|黃疸|積聚|癥瘕|鼓脹|蠱脹|消渴|勞瘵")
OBSTETRIC_RX = re.compile(r"産|胎|妊|孕|月經|經水|崩漏|帶下")
PAEDIATRIC_RX = re.compile(r"小兒|嬰|孩")
THEORY_RX = re.compile(r"脉|脈|《內經》|《靈樞》|《難經》")

STOOL_CATS = ("Diarrhea (泄瀉) C2/C3", "Dysentery (痢疾) C2/C3", "Dawn Diarrhea (五更泄) C2",
              "Mucus/abnormal stool C3")
CONST_CAT = "Constipation (便秘) C2/C3"
LINK_CAT = "Painful Diarrhea (痛瀉) C1"
PAIN_CAT = "Abdominal pain (腹痛) C1"


def load_patterns(cfg=None):
    cfg = cfg or load_config()
    return [(r["pattern"], [norm(t) for t in r["terms"].split("|")]) for r in read_csv("data/pattern_terms.csv")]


def annotate(u, dictionary, patterns):
    t = u["norm"]
    hits = [d for d in dictionary if d["norm"] in t]
    cats = {}
    for d in hits:
        cats.setdefault(d["category"], []).append(d["term"])
    diarrhea = [x for c in STOOL_CATS for x in cats.get(c, [])]
    const = cats.get(CONST_CAT, [])
    link = cats.get(LINK_CAT, [])
    pain = cats.get(PAIN_CAT, [])
    if diarrhea and const:
        habit = "M"
    elif diarrhea or link:
        habit = "D"
    elif const:
        habit = "C"
    else:
        habit = "U"
    pats = [p for p, terms in patterns if any(x in t for x in terms)]
    return dict(
        flag_link_terms="|".join(link),
        flag_pain_terms="|".join(pain),
        flag_stool_terms="|".join(diarrhea + const),
        flag_chronicity="|".join(sorted(set(CHRONIC_RX.findall(t)))),
        flag_acute_febrile="|".join(sorted(set(ACUTE_RX.findall(t)))),
        flag_systemic="|".join(sorted(set(SYSTEMIC_RX.findall(t)))),
        flag_obstetric="|".join(sorted(set(OBSTETRIC_RX.findall(t)))),
        flag_paediatric="|".join(sorted(set(PAEDIATRIC_RX.findall(t)))),
        flag_theory_or_pulse="|".join(sorted(set(THEORY_RX.findall(t)))),
        auto_bowel_habit=habit,
        auto_patterns="|".join(pats),
    )
