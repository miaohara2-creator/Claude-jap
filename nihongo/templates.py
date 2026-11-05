"""Gerador local de reserva (sem API).

Usa (1) um corpus de frases escritas a mao e (2) moldes periphrasticos em
portugues que podem ser montados mecanicamente a partir do infinitivo do
verbo -- "eu costumo beber", "agora eu estou bebendo", "eu quero beber" --
evitando conjugar o portugues, o que exigiria formas irregulares.

As frases produzidas aqui passam pela mesma validacao das frases da Claude.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .vocab import Item

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Template:
    pt: str          # molde da frase em portugues
    ja: str          # molde da frase em japones
    kana: str        # molde da leitura
    keyword: str     # molde do trecho destacado
    time_slot: bool = False   # aceita adverbio de tempo no inicio
    needs: tuple[str, ...] = ()  # item_ids que precisam estar conhecidos


#: Expressoes de tempo compativeis com habito (usadas em 〜ます/〜ません).
HABIT_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    ("毎日|base", "Todos os dias", "毎日、", "まいにち、"),
    ("いつも|base", "Sempre", "いつも", "いつも"),
    ("時々|base", "Às vezes", "時々", "ときどき"),
)

VERB_TEMPLATES: dict[str, tuple[Template, ...]] = {
    "masu": (Template("{TIME}eu costumo {INF}.", "{TIME_JA}{K}。", "{TIME_KANA}{KR}。",
                      "costumo {INF}", time_slot=True),),
    "masen": (Template("{TIME}eu não costumo {INF}.", "{TIME_JA}{K}。", "{TIME_KANA}{KR}。",
                       "não costumo {INF}", time_slot=True),),
    "mashita": (Template("Eu acabei de {INF}.", "{K}。", "{KR}。", "acabei de {INF}"),),
    "masen_deshita": (Template("Eu não cheguei a {INF}.", "{K}。", "{KR}。",
                               "não cheguei a {INF}"),),
    "te_imasu": (
        Template("Agora eu estou {GER}.", "今、{K}。", "いま、{KR}。", "estou {GER}",
                 needs=("今|base",)),
        Template("Eu estou {GER}.", "{K}。", "{KR}。", "estou {GER}"),
    ),
    "tai": (Template("Eu quero {INF}.", "{K}です。", "{KR}です。", "quero {INF}"),),
    "masho": (Template("Vamos {INF}!", "{K}。", "{KR}。", "Vamos {INF}"),),
    "potential": (Template("Eu consigo {INF}.", "{K}。", "{KR}。", "consigo {INF}"),),
}

NOUN_TEMPLATES: tuple[Template, ...] = (
    Template("Isto é {PT}.", "これは{K}です。", "これは{KR}です。", "{PT}"),
    Template("Aquilo também é {PT}.", "あれも{K}です。", "あれも{KR}です。", "{PT}"),
)

ADJ_I_TEMPLATES: dict[str, tuple[Template, ...]] = {
    "adj_plain": (Template("Isto é {PT}.", "これは{K}です。", "これは{KR}です。", "{PT}"),),
    "adj_neg": (Template("Isto não é {PT}.", "これは{K}です。", "これは{KR}です。",
                         "não é {PT}"),),
    "adj_past": (Template("Isso era {PT}.", "それは{K}です。", "それは{KR}です。",
                          "era {PT}"),),
    "adj_past_neg": (Template("Isso não era {PT}.", "それは{K}です。", "それは{KR}です。",
                              "não era {PT}"),),
}

ADJ_NA_TEMPLATES: dict[str, tuple[Template, ...]] = {
    "adj_plain": (Template("Isto é {PT}.", "これは{K}。", "これは{KR}。", "{PT}"),),
    "adj_neg": (Template("Isto não é {PT}.", "これは{K}。", "これは{KR}。", "não é {PT}"),),
    "adj_past": (Template("Isso era {PT}.", "それは{K}。", "それは{KR}。", "era {PT}"),),
}


def first_gloss(pt: str) -> str:
    """Primeiro significado de uma glosa como "ter; segurar" ou "alto (preço)"."""
    return pt.split(";")[0].split("(")[0].strip()


def gerund(infinitive: str) -> str:
    """Gerúndio português a partir do infinitivo (regular para -ar/-er/-ir)."""
    inf = infinitive.strip()
    for ending, repl in (("ar", "ando"), ("er", "endo"), ("ir", "indo")):
        if inf.endswith(ending):
            return inf[: -len(ending)] + repl
    return inf


def corpus_entries() -> dict[str, list[dict]]:
    """Frases escritas a mao, indexadas por item_id."""
    path = DATA_DIR / "corpus.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for entry in payload.get("sentences", []):
        out.setdefault(entry["item_id"], []).append(entry)
    return out


def _templates_for(item: Item) -> tuple[Template, ...]:
    if item.word_type.startswith("verb"):
        return VERB_TEMPLATES.get(item.form_id, ())
    if item.word_type == "adj-i":
        return ADJ_I_TEMPLATES.get(item.form_id, ())
    if item.word_type == "adj-na":
        return ADJ_NA_TEMPLATES.get(item.form_id, ())
    if item.word_type in ("noun", "pronoun"):
        return NOUN_TEMPLATES
    return ()


def build_local_sentence(
    item: Item, known_ids: set[str], rng: random.Random | None = None
) -> dict | None:
    """Monta uma frase com os moldes locais, ou None se a forma nao tiver molde."""
    rng = rng or random.Random()
    candidates = [t for t in _templates_for(item)
                  if all(n in known_ids for n in t.needs)]
    if not candidates:
        return None
    tpl = rng.choice(candidates)

    gloss = first_gloss(item.pt)
    ger = gerund(gloss)

    time_pt = time_ja = time_kana = ""
    if tpl.time_slot:
        options = [t for t in HABIT_SLOTS if t[0] in known_ids]
        if options:
            _, time_pt, time_ja, time_kana = rng.choice(options)

    fields = {"INF": gloss, "GER": ger, "PT": gloss}
    pt = tpl.pt.format(TIME=f"{time_pt} " if time_pt else "", **fields)
    if not time_pt:
        pt = pt[0].upper() + pt[1:]
    return {
        "pt": pt,
        "keyword_pt": tpl.keyword.format(**fields),
        "ja": tpl.ja.format(TIME_JA=time_ja, K=item.surface),
        "ja_reading": tpl.kana.format(TIME_KANA=time_kana, KR=item.reading),
        "words_used": [item.lemma],
        "note": (
            f"{item.form_label}. Frase montada pelo gerador local — "
            "configure a API da Claude para frases com mais contexto."
        ),
    }
