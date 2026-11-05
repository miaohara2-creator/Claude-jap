"""Carregamento do vocabulario e expansao em itens de estudo.

Um *item* e a unidade que recebe um cartao FSRS. Para palavras invariaveis
(substantivos, adverbios...) o item e a propria palavra. Para verbos e
adjetivos, cada forma conjugada e um item independente -- por exemplo
`飲みます`, `飲まない` e `飲ませられる` sao tres palavras-chave distintas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .conjugation import (
    FORM_SPECS,
    LEVEL_ORDER,
    conjugate,
    form_catalog,
    inflects,
    level_index,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BASE_FORM = "base"


@dataclass(frozen=True)
class Item:
    """Uma palavra-chave estudavel."""

    item_id: str
    lemma: str            # escrita do lema (ex. 飲む)
    lemma_reading: str    # leitura do lema
    word_type: str
    pt: str               # significado em portugues
    form_id: str          # "base" para palavras invariaveis
    surface: str          # escrita da forma (ex. 飲みません)
    reading: str          # leitura da forma
    form_label: str       # descricao da forma em portugues
    form_hint: str        # como o portugues sinaliza essa forma
    lemma_level: str      # nivel JLPT do lema
    level: str            # nivel efetivo = max(nivel do lema, nivel da forma)
    lemma_rank: int       # ordem do lema dentro do nivel
    form_order: int       # ordem pedagogica da forma
    alt: tuple[str, ...] = ()   # escritas alternativas aceitas

    @property
    def is_inflected(self) -> bool:
        return self.form_id != BASE_FORM

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (level_index(self.level), self.lemma_rank, self.form_order)

    def label(self) -> str:
        """Rotulo legivel: significado + forma."""
        if self.is_inflected:
            return f"{self.pt} — {self.form_label}"
        return self.pt

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "lemma": self.lemma,
            "lemma_reading": self.lemma_reading,
            "word_type": self.word_type,
            "pt": self.pt,
            "form_id": self.form_id,
            "surface": self.surface,
            "reading": self.reading,
            "form_label": self.form_label,
            "form_hint": self.form_hint,
            "level": self.level,
            "lemma_level": self.lemma_level,
            "label": self.label(),
            "alt": list(self.alt),
        }


def _max_level(a: str, b: str) -> str:
    return a if level_index(a) >= level_index(b) else b


def load_raw(data_dir: Path | None = None) -> list[dict]:
    """Le os arquivos data/vocab_n*.json na ordem N5 -> N1."""
    data_dir = data_dir or DATA_DIR
    out: list[dict] = []
    for level in LEVEL_ORDER:
        path = data_dir / f"vocab_{level.lower()}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rank, entry in enumerate(payload["words"], start=1):
            out.append({**entry, "level": payload["level"], "rank": rank})
    return out


def build_items(data_dir: Path | None = None) -> list[Item]:
    """Expande o vocabulario bruto em itens estudaveis, em ordem pedagogica."""
    items: list[Item] = []
    for entry in load_raw(data_dir):
        word, reading = entry["w"], entry["r"]
        wtype, pt = entry["t"], entry["pt"]
        lemma_level, rank = entry["level"], entry["rank"]
        alt = tuple(entry.get("alt", ()))

        if not inflects(wtype):
            items.append(
                Item(
                    item_id=f"{word}|{BASE_FORM}",
                    lemma=word,
                    lemma_reading=reading,
                    word_type=wtype,
                    pt=pt,
                    form_id=BASE_FORM,
                    surface=word,
                    reading=reading,
                    form_label="palavra invariável",
                    form_hint="",
                    lemma_level=lemma_level,
                    level=lemma_level,
                    lemma_rank=rank,
                    form_order=0,
                    alt=alt,
                )
            )
            continue

        for conj in conjugate(word, reading, wtype):
            spec = conj.spec
            items.append(
                Item(
                    item_id=f"{word}|{conj.form_id}",
                    lemma=word,
                    lemma_reading=reading,
                    word_type=wtype,
                    pt=pt,
                    form_id=conj.form_id,
                    surface=conj.surface,
                    reading=conj.reading,
                    form_label=spec.pt_label,
                    form_hint=spec.pt_hint,
                    lemma_level=lemma_level,
                    level=_max_level(lemma_level, spec.level),
                    lemma_rank=rank,
                    form_order=spec.order,
                    alt=alt,
                )
            )

    items.sort(key=lambda it: it.sort_key)
    return items


class Vocabulary:
    """Indice em memoria de todos os itens estudaveis."""

    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self.by_id = {it.item_id: it for it in items}
        self.by_level: dict[str, list[Item]] = {lv: [] for lv in LEVEL_ORDER}
        for it in items:
            self.by_level.setdefault(it.level, []).append(it)
        # formas do mesmo lema, em ordem de desbloqueio
        self.by_lemma: dict[str, list[Item]] = {}
        for it in items:
            self.by_lemma.setdefault(it.lemma, []).append(it)
        for forms in self.by_lemma.values():
            forms.sort(key=lambda it: (level_index(it.level), it.form_order))

    @classmethod
    def load(cls, data_dir: Path | None = None) -> "Vocabulary":
        return cls(build_items(data_dir))

    def get(self, item_id: str) -> Item | None:
        return self.by_id.get(item_id)

    def previous_form(self, item: Item) -> Item | None:
        """Forma que deve ser aprendida imediatamente antes desta."""
        forms = self.earlier_forms(item)
        return forms[-1] if forms else None

    def earlier_forms(self, item: Item) -> list[Item]:
        """Todas as formas do mesmo lema que vêm antes desta na ordem pedagógica."""
        forms = self.by_lemma.get(item.lemma, [])
        for i, cand in enumerate(forms):
            if cand.item_id == item.item_id:
                return forms[:i]
        return []

    def level_counts(self) -> dict[str, int]:
        return {lv: len(self.by_level.get(lv, [])) for lv in LEVEL_ORDER}

    def __len__(self) -> int:
        return len(self.items)
